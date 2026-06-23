from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.dataset import scan_yolo_dataset
from app.exporter import export_relabel_dataset, export_split_dataset, load_selection_state, save_selection_state
from app.yolo import parse_class_names, parse_yolo_label_file


class CoreTests(unittest.TestCase):
    def test_parse_multiple_yolo_boxes(self):
        with TemporaryDirectory() as tmp:
            label = Path(tmp) / "sample.txt"
            label.write_text(
                "0 0.5 0.5 0.2 0.3\n"
                "2 0.1 0.2 0.3 0.4\n",
                encoding="utf-8",
            )

            boxes = parse_yolo_label_file(label)

        self.assertEqual(len(boxes), 2)
        self.assertEqual(boxes[0].class_id, 0)
        self.assertEqual(boxes[1].class_id, 2)

    def test_scan_and_export_dataset(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "dataset"
            image_dir = root / "images" / "train"
            label_dir = root / "labels" / "train"
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)
            (image_dir / "a.jpg").write_bytes(b"fake image")
            (label_dir / "a.txt").write_text("1 0.5 0.5 0.4 0.4\n", encoding="utf-8")

            items = scan_yolo_dataset(root)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].label_count, 1)

            output = Path(tmp) / "relabel"
            count = export_relabel_dataset(items, {0}, output, clear_labels=False)

            self.assertEqual(count, 1)
            self.assertTrue((output / "images" / "train" / "a.jpg").exists())
            self.assertEqual((output / "labels" / "train" / "a.txt").read_text(encoding="utf-8").strip(), "1 0.5 0.5 0.4 0.4")

    def test_parse_block_class_names(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data.yaml").write_text(
                "names:\n"
                "  0: person\n"
                "  1: car\n",
                encoding="utf-8",
            )

            self.assertEqual(parse_class_names(root), {0: "person", 1: "car"})

    def test_scan_jpegimages_and_yolo_labels_dataset(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "dataset"
            image_dir = root / "JPEGImages"
            label_dir = root / "yolo_labels"
            visualization_dir = root / "Visualization"
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)
            visualization_dir.mkdir(parents=True)
            (image_dir / "frame.png").write_bytes(b"fake image")
            (visualization_dir / "frame.png").write_bytes(b"visualized image")
            (label_dir / "frame.txt").write_text(
                "0 0.5 0.5 0.2 0.2\n"
                "1 0.2 0.3 0.1 0.1\n",
                encoding="utf-8",
            )

            items = scan_yolo_dataset(root)

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].label_count, 2)
            self.assertEqual(items[0].relative_image_path.as_posix(), "frame.png")
            self.assertEqual(items[0].relative_label_path.as_posix(), "frame.txt")

    def test_export_split_dataset(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "dataset"
            image_dir = root / "images" / "train"
            label_dir = root / "labels" / "train"
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)

            for name, label in [
                ("a.jpg", "0 0.5 0.5 0.2 0.2\n"),
                ("b.jpg", "1 0.5 0.5 0.2 0.2\n"),
                ("c.jpg", "2 0.5 0.5 0.2 0.2\n"),
            ]:
                (image_dir / name).write_bytes(b"fake image")
                (label_dir / Path(name).with_suffix(".txt")).write_text(label, encoding="utf-8")

            items = scan_yolo_dataset(root)
            output = Path(tmp) / "split"
            counts = export_split_dataset(
                items,
                relabel_indices={0},
                delete_indices={1},
                output_root=output,
                clear_relabel_labels=True,
            )

            self.assertEqual(counts, {"relabel": 1, "delete": 1, "qualified": 1})
            self.assertTrue((output / "relabel" / "images" / "train" / "a.jpg").exists())
            self.assertTrue((output / "delete" / "labels" / "train" / "b.txt").exists())
            self.assertTrue((output / "qualified" / "images" / "train" / "c.jpg").exists())
            self.assertEqual((output / "relabel" / "labels" / "train" / "a.txt").read_text(encoding="utf-8"), "")

    def test_state_restores_by_relative_path(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "dataset"
            image_dir = root / "images"
            label_dir = root / "labels"
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)

            for name in ["a.jpg", "b.jpg", "c.jpg"]:
                (image_dir / name).write_bytes(b"fake image")
                (label_dir / Path(name).with_suffix(".txt")).write_text("", encoding="utf-8")

            items = scan_yolo_dataset(root)
            state_path = Path(tmp) / "state.json"
            save_selection_state(state_path, {1}, {2}, 1, items)

            shuffled_items = [items[2], items[0], items[1]]
            relabel, delete, current = load_selection_state(state_path, shuffled_items)

            self.assertEqual(relabel, {2})
            self.assertEqual(delete, {0})
            self.assertEqual(current, 2)


if __name__ == "__main__":
    unittest.main()

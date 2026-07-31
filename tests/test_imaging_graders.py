from medphys_agentbench.scoring import grade_bounding_box_iou, grade_grid_mask_dice


def test_bounding_box_iou_accepts_identical_box() -> None:
    grade = grade_bounding_box_iou(
        {"field": "bbox", "expected": [1, 2, 9, 10], "minimum_iou": 0.5},
        {"bbox": [1, 2, 9, 10]},
    )
    assert grade.passed is True
    assert grade.score == 1.0


def test_bounding_box_iou_rejects_degenerate_and_disjoint_boxes() -> None:
    degenerate = grade_bounding_box_iou(
        {"field": "bbox", "expected": [1, 2, 9, 10]}, {"bbox": [3, 3, 3, 8]}
    )
    disjoint = grade_bounding_box_iou(
        {"field": "bbox", "expected": [1, 2, 9, 10], "minimum_iou": 0.01},
        {"bbox": [20, 20, 25, 25]},
    )
    assert degenerate.passed is False
    assert disjoint.passed is False
    assert disjoint.score == 0.0


def test_grid_mask_dice_handles_overlap_and_empty_masks() -> None:
    overlap = grade_grid_mask_dice(
        {"field": "cells", "expected": [[0, 0], [0, 1], [1, 1]], "minimum_dice": 0.6},
        {"cells": [[0, 0], [1, 1], [4, 4]]},
    )
    empty = grade_grid_mask_dice(
        {"field": "cells", "expected": [], "minimum_dice": 1.0}, {"cells": []}
    )
    assert overlap.passed is True
    assert overlap.score == 0.66666667
    assert empty.passed is True
    assert empty.score == 1.0


def test_grid_mask_dice_rejects_duplicate_or_invalid_cells() -> None:
    duplicate = grade_grid_mask_dice(
        {"field": "cells", "expected": [[0, 0]]}, {"cells": [[0, 0], [0, 0]]}
    )
    negative = grade_grid_mask_dice(
        {"field": "cells", "expected": [[0, 0]]}, {"cells": [[-1, 0]]}
    )
    assert duplicate.passed is False
    assert negative.passed is False

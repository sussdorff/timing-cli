# tdd_evidence_v1

Debrief envelope for one bead's TDD slices. The test author returns this after
RED; the loop fills GREEN after the implementer session.

```json
{
  "envelope": "tdd_evidence_v1",
  "bead_id": "<id>",
  "seams": [{"name": "", "interface": ""}],
  "slices": [
    {
      "id": "slice-1",
      "seam": "",
      "red": {"command": "", "exit": 1, "reason": ""},
      "green": {"command": "", "exit": 0, "status": "pending"},
      "expected_values": [
        {
          "name": "",
          "value": "",
          "source_kind": "ig_profile",
          "source": "",
          "test_path": "",
          "ig_canonical": "",
          "element": ""
        }
      ]
    }
  ]
}
```

`source_kind` is one of `generated_fixture`, `ig_profile`, `oracle`,
`worked_example`, `source_value_profile`. The authored test must contain the
literal expected value and the provenance tokens. Relabeled implementation
output is rejected by `verify_expected_sources.py`.

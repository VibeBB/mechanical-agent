# ADR-0008: ISO 7200 title block sourced from the brief

## Status

Accepted

## Context

The DXF title block printed `DESIGN`, `PART`, `REV A` and the generator,
so a sheet could not say who owns it, who prepared and approved it, when
it was issued, or which brief it was generated from. wire-agent rebuilt
its harness title block on ISO 7200:2004 (wire-agent ADR on drawing
frames); the family keeps one policy across drawing producers.

## Decision

- `DesignBrief.drawing` (`DrawingInfo`) carries the ISO 7200 fields the
  brief cannot derive. Every field is optional; unset fields print `—`
  so a blank reads as "not yet stated", not as a layout gap.
- The document status is derived: `Released` needs `approved_by` and
  `date_of_issue`, `In approval` needs `approved_by`, otherwise
  `In preparation`. `date_of_issue` without `approved_by` is rejected —
  only approved drawings issue.
- Rows read top to bottom and end in the identification zone at the
  bottom-right corner: `OWNER`, `ID NO.` + `REV`, `DATE` + `LANG` +
  `SHEET`.
- `BRIEF SHA` prints the first 16 hex digits of `brief_sha256`, tying the
  sheet to the exact brief bytes; `GENERATOR` names the tool and version.
- No producer logo or VibeBB mark is drawn. The generator row identifies
  the tool; the legal owner is the user's organisation.
- Notes and title blocks share one column width so the column never
  narrows above the title block or crowds the part.

## Consequences

Adding `drawing` changes `brief_sha256` for every brief, so intake
sidecars must be regenerated. DXF consumers that parsed the old
`DESIGN`/`PART` rows must read `TITLE`/`ID NO.` instead. Owner logos are
not embedded in DXF (an IMAGE entity needs an external file); wire-agent
remains the only producer with an owner logo.

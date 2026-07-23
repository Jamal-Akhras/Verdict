# The real-model quality pass

Before charging anyone, the feasibility verdicts must be calibrated - a
validator that says "validate" to everything is astrology with provenance
headers. This is the one-command check.

## Run it

```bash
cd apps/api
# free real AI: put a Gemini key (https://aistudio.google.com, no card) in .env
echo "GEMINI_API_KEY=your-key" >> .env

python -m scripts.quality_pass              # 6 golden briefs x 3 repeats
```

Expect roughly $0.05-$0.30 total on Gemini flash/pro pricing per full pass
(free within the daily free-tier quota), or ~$1-2 on OpenAI/Anthropic.

## What it checks

| Check | Meaning |
|---|---|
| Band hit rate | Each golden brief has a verdict band a calibrated analyst should land in (a no-budget "replace Facebook" idea must NOT get "build"). Threshold: 70%. |
| Flip rate | The same brief run 3x should not swing between verdicts. Flips = prompt is under-constrained. |
| Regulated-health probe | The therapist-notes brief must not score risk_compliance above 7. |
| Validator failures | Rubric weights, categories, and story ACs are enforced by Pydantic validators; failures surface here. |

## When it fails

Tune `app/prompts/feasibility.md` (the verdict bands and rubric guidance),
not the code. Re-run after every prompt change - the script is cheap enough
to be the regression test for prompt edits. Every run is also fully logged
in ModelCall rows, so you can inspect exactly what the model said.

## Definition of done for "one real quality pass"

1. `python -m scripts.quality_pass` exits 0 with real keys.
2. Read one full run's artifacts end to end (intake -> verdict -> PRD ->
   tech plan -> build plan) for the gym brief and one of YOUR real ideas;
   fix any section that reads like generic filler by tightening its prompt.
3. Re-run the script once more to confirm no regression.

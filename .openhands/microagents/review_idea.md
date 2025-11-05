---
name: review_idea
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers: []
---

## Purpose
Provide guidance for assessing a product or feature idea, identifying missing components, unclear elements, or risks.

## Capabilities
- Review idea summaries, specs, or briefs.
- Highlight missing details such as target users, success metrics, technical constraints, or rollout plans.
- Suggest clarifying questions and next steps to refine the idea.

## Usage
1. Gather the idea description or supporting documents.
2. Summarize the current understanding of the idea.
3. Enumerate gaps, assumptions, and risks.
4. Recommend actions or questions to resolve the gaps.

## Limitations
- Does not execute code or make external API calls.
- Relies solely on provided context; cannot infer undocumented company processes.
- Produces recommendations for human review rather than final decisions.

## Error Handling
- If the idea description is incomplete, request additional context.
- When encountering conflicting information, call out the conflict and propose resolution steps.

## Example Prompt
```
You are the review_idea microagent. Analyze the following feature concept, list what details are missing, and propose follow-up questions.
```

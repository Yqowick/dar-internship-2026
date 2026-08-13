# AI Tooling Usage and Impact

## Tools used

### GitHub Copilot

GitHub Copilot supported code completion, refactoring, comments, and consistency checks. The repository includes `.github/copilot-instructions.md`, an actual AI customization artifact that defines the RAG architecture, grounding rules, MongoDB persistence model, frontend conventions, API behavior, and Git workflow.

### ChatGPT

ChatGPT supported architecture planning, beginner-friendly explanation, debugging, implementation review, documentation drafting, and step-by-step terminal guidance. Suggested changes were applied only after local review and execution.

### Claude

Claude was used to create and visually polish the final three-slide presentation based on the completed project and the supervisor's required structure.

## Impact

AI tooling accelerated repetitive implementation work and helped keep the multi-service project organized. The most important benefits were:

- faster iteration across Python, React, TypeScript, MongoDB, and Docker;
- clearer explanations of unfamiliar concepts;
- consistent naming and separation of responsibilities;
- faster identification of frontend and guided-tour bugs;
- professional documentation and presentation preparation.

## Responsible use

AI outputs were not accepted blindly. Every change was reviewed in context, applied to a feature branch, compiled or executed locally, and checked against the required behavior. The project-specific Copilot instructions prevent suggestions that would bypass retrieval, use outside knowledge, weaken the refusal message, expose secrets, or replace MongoDB persistence with browser-only storage.

## Customization artifact

The checked-in artifact is:

`.github/copilot-instructions.md`

It demonstrates how a general AI coding assistant was converted into a project-aware assistant with explicit architecture, safety, coding, and delivery constraints.

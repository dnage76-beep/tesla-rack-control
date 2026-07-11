We are seeking a cost-benefit analysis of several possible paths for enabling a Comma 3X to operate on a Tesla Model S.

Background

Our original goal was to use the existing Tesla Model S support developed by BogGyver and previously distributed through Tinkla harnesses. Tinkla no longer sells the required harnesses, and the associated codebase appears abandoned (last commit approximately two years ago).

Based on discussions in the openpilot community and the GitHub issue below, the legacy BogGyver/Tinkla solution appears to require AGNOS 8:

https://github.com/commaai/openpilot/issues/28726

We currently have a Comma 3X running a modern AGNOS release (AGNOS 18.4). We have been unable to downgrade to AGNOS 8. Information from external sources suggests that changes to the AGNOS partitioning/cache system may prevent a straightforward downgrade using the custom software installation mechanism. We have not yet identified a reliable downgrade procedure.

Options Under Consideration
Option 1: Restore the Legacy BogGyver/Tinkla Solution
Determine how to downgrade the Comma 3X from AGNOS 18.4 to AGNOS 8.
Install and run the legacy Tesla Model S codebase.
Resolve any compatibility issues required to make the historical solution functional.
Option 2: Add Tesla Model S Support to Current Openpilot
Fork the latest official openpilot repository.
Implement Tesla Model S support on top of the current codebase.
Reuse any applicable reverse-engineering work, documentation, findings, or code from BogGyver's project where possible.
Maintain compatibility with current AGNOS and openpilot versions.
Option 3: Develop a Self-Driving Stack from Scratch
Build on an existing RC vehicle platform.
Implement perception, planning, and control systems independently.
Determine whether to use classical computer vision, machine learning, or a trained AI model for decision-making.
Develop the required software, training, validation, and integration infrastructure.
Requested Analysis

Please research the technical requirements and constraints associated with each option and provide:

A description of the major technical challenges involved.
Estimated difficulty and complexity.
Approximate time and effort required.
Key risks and unknowns.
Probability of success.
Relative cost-benefit comparison.

The primary objective is to identify the path that minimizes effort while maximizing the likelihood of a successful outcome. We are not requesting a complete solution, only an informed comparison of the available approaches based on the current technical landscape.

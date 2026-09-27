# Weekly Notes Feature Prompt

Implement or improve My Weekly Notes in SkillSpring.

Requirements:
- display the current week's learning notes;
- support creating/updating a note where the existing application architecture allows it;
- preserve note content safely;
- provide clear save/update feedback;
- avoid stale UI after save;
- handle empty notes gracefully;
- keep the UI responsive.

For every save/update:
1. send the correct request;
2. verify backend response;
3. update the visible UI;
4. confirm persistence if persistence is part of the existing design.

Do not silently fake successful persistence.

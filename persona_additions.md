
### 6. The Computer Vision Researcher (ReID)
*   **Perspective:** Solve the "Object Permanence" problem across disjoint camera views.
*   **Strategic Idea:** **Multi-Camera Re-Identification (ReID)**. Implement a DeepSORT or Siamese Network layer to assign unique IDs to subjects based on visual features (clothing, gait) rather than just spatial overlap. This enables tracking a specific "Subject #12" as they move from the Driveway to the Backyard, flagging the *sequence* of movement as a higher risk vector ("Casing the property") than isolated detections.

### 7. The Data Scientist (Pattern of Life)
*   **Perspective:** Security is about anomalies in routine, not just object detection.
*   **Strategic Idea:** **Statistical "Pattern of Life" Profiling**. Instead of heavy Vector DBs, implement lightweight **Frequency Maps** (structured SQL/JSON) to track routine occurrences (e.g., "Mail truck usually arrives M-F at 2pm"). This allows the system to flag purely contextual anomalies (e.g., "Mail truck detected at 3am on Sunday") based on statistical deviation (<5% probability) rather than just visual threat classification.

# AI Enrichment Data in Event Details

> Understanding the advanced AI analysis displayed for each security event.

**Time to read:** ~8 min
**Prerequisites:** [Viewing Events](viewing-events.md)

---

## Overview

When you view an event in detail, the system shows AI Enrichment Analysis - additional information extracted by specialized AI models that run on each detection. This enrichment data provides deeper insight into what was detected, helping you understand context beyond basic object detection.

The AI enrichment panel appears in the Event Detail Modal, below the Detected Objects list, when enrichment data is available for a detection.

---

## What is AI Enrichment?

Basic object detection tells you "there is a person" or "there is a vehicle." AI enrichment goes further:

- **For vehicles:** What type? What color? Any damage? Is there a license plate?
- **For people:** What are they wearing? Are they carrying anything? Face visible?
- **For animals:** Is it a cat or dog? Is it likely a household pet?
- **For the scene:** What's the weather? What's the image quality?

This additional context helps the system assign more accurate risk scores and helps you understand situations at a glance.

---

## Finding AI Enrichment Data

AI enrichment data appears in the Event Detail Modal:

1. Click any event in the Live Activity Feed or Event Timeline
2. In the popup, scroll down past the Detected Objects section
3. Look for the **AI Enrichment Analysis** panel with accordion sections

<!-- SCREENSHOT: AI Enrichment Panel
Location: Event Detail Modal, below Detected Objects section
Shows: AI Enrichment Analysis panel with expandable accordion sections for Vehicle, Person, License Plate, etc. with confidence badges
Size: 800x400 pixels (2:1 aspect ratio)
Alt text: AI Enrichment Analysis panel showing collapsible sections for different types of enrichment data with confidence percentages
-->
<!-- Screenshot: AI Enrichment Analysis panel with expandable sections -->

_Caption: The AI Enrichment Analysis panel shows additional context extracted by specialized AI models._

---

## Enrichment Data Types

### Vehicle Information

When a vehicle is detected, the system analyzes:

| Field          | Description                                      | Example Values                      |
| -------------- | ------------------------------------------------ | ----------------------------------- |
| **Type**       | Vehicle category                                 | Sedan, SUV, Pickup, Van, Truck      |
| **Color**      | Primary vehicle color                            | Silver, Black, White, Red, Blue     |
| **Damage**     | Detected damage types (security relevant)        | Cracks, Dents, Scratches, Tire Flat |
| **Commercial** | Whether it appears to be a delivery/work vehicle | Badge shown if detected             |

**Damage Types (Security Relevant):**

- **Glass Shatter** - Broken windows (possible break-in)
- **Lamp Broken** - Damaged headlights/taillights
- **Cracks, Dents, Scratches** - Body damage
- **Tire Flat** - Deflated or damaged tires

<!-- SCREENSHOT: Vehicle Enrichment Section
Location: Expanded Vehicle section in AI Enrichment panel
Shows: Vehicle accordion expanded showing Type, Color, Damage fields with confidence badge
Size: 600x200 pixels (3:1 aspect ratio)
Alt text: Vehicle enrichment section showing sedan type, silver color, and commercial vehicle badge
-->
<!-- Screenshot: Expanded Vehicle enrichment section -->

_Caption: Vehicle enrichment shows type, color, and any detected damage._

### Person Information

When a person is detected, the system analyzes:

| Field                 | Description                         | Example Values                       |
| --------------------- | ----------------------------------- | ------------------------------------ |
| **Clothing**          | General clothing description        | Red t-shirt, Blue jeans, Dark jacket |
| **Action**            | What the person appears to be doing | Walking, Standing, Crouching         |
| **Carrying**          | Items being carried                 | Backpack, Package, Bag               |
| **Suspicious Attire** | Security-relevant clothing flags    | Face covered, All-dark clothing      |
| **Service Uniform**   | Delivery/service worker clothing    | Visible if detected                  |

**Security Flags:**

- **Suspicious Attire** (yellow warning) - Face coverings, all-dark clothing at night, masks
- **Service Uniform** (blue info) - Delivery driver uniforms, maintenance worker clothing

<!-- SCREENSHOT: Person Enrichment Section
Location: Expanded Person section in AI Enrichment panel
Shows: Person accordion expanded showing Clothing, Action, Carrying fields with flag badges
Size: 600x250 pixels (2.4:1 aspect ratio)
Alt text: Person enrichment section showing clothing description, action, and suspicious attire warning badge
-->
<!-- Screenshot: Expanded Person enrichment section with security flags -->

_Caption: Person enrichment shows clothing, behavior, and security-relevant flags._

### License Plate Detection

When a license plate is detected on a vehicle:

| Field          | Description                      | Format     |
| -------------- | -------------------------------- | ---------- |
| **Plate Text** | OCR-extracted plate number       | ABC-1234   |
| **Confidence** | How confident the OCR reading is | Percentage |

The plate text is displayed in a highlighted box for easy reading. If the plate was detected but the text couldn't be read clearly, it shows as "[unreadable]".

<!-- SCREENSHOT: License Plate Enrichment Section
Location: Expanded License Plate section in AI Enrichment panel
Shows: License Plate accordion expanded showing OCR text in highlighted monospace font
Size: 600x150 pixels (4:1 aspect ratio)
Alt text: License plate enrichment showing detected plate number ABC-1234 with confidence percentage
-->
<!-- Screenshot: Expanded License Plate section with OCR text -->

_Caption: License plate detection shows the extracted plate number when readable._

### Pet Identification

When a cat or dog is detected:

| Field          | Description                        | Example Values  |
| -------------- | ---------------------------------- | --------------- |
| **Type**       | Animal type                        | Cat, Dog        |
| **Breed**      | Detected breed (when identifiable) | Labrador, Tabby |
| **Confidence** | Classification confidence          | Percentage      |

Pet detection helps reduce false alarms - when the system identifies a high-confidence household pet with no other concerning factors, it can automatically lower the risk score.

<!-- SCREENSHOT: Pet Enrichment Section
Location: Expanded Pet section in AI Enrichment panel
Shows: Pet accordion expanded showing Type (Dog) and Breed fields with confidence badge
Size: 600x150 pixels (4:1 aspect ratio)
Alt text: Pet enrichment section showing detected dog with confidence percentage
-->
<!-- Screenshot: Expanded Pet enrichment section -->

_Caption: Pet identification helps distinguish household pets from security threats._

### Weather Conditions

The system detects weather from the camera image:

| Field          | Description          | Example Values         |
| -------------- | -------------------- | ---------------------- |
| **Condition**  | Detected weather     | Clear, Rain, Snow, Fog |
| **Confidence** | Detection confidence | Percentage             |

Weather context helps interpret events - a person running in rain may be rushing to get inside rather than fleeing a scene.

### Image Quality Assessment

The system assesses image quality for each detection:

| Field             | Description                    | Interpretation         |
| ----------------- | ------------------------------ | ---------------------- |
| **Quality Score** | Overall image quality (0-100%) | Higher is better       |
| **Issues**        | Detected quality problems      | Blur, Low Light, Noise |

**Quality Issues:**

- **Blur** - Image is blurry (fast motion or camera focus issue)
- **Low Light** - Dark/underexposed image
- **Overexposed** - Too bright, washed out
- **Noise** - Grainy/noisy image

**Security Note:** Sudden quality drops can indicate camera tampering. If the system detects an unexpected quality change, it flags this for review.

---

## Understanding Confidence Scores

Each enrichment section shows a confidence badge indicating how certain the AI is about its analysis:

| Confidence Level    | Color  | Meaning                          |
| ------------------- | ------ | -------------------------------- |
| **High (>80%)**     | Green  | AI is confident in the result    |
| **Medium (50-80%)** | Yellow | AI is moderately confident       |
| **Low (<50%)**      | Red    | AI is uncertain; verify manually |

**Interpretation Tips:**

- High confidence results can generally be trusted
- Medium confidence may need human verification
- Low confidence should be manually reviewed; the AI is uncertain

---

## Accordion Navigation

The AI Enrichment panel uses collapsible accordion sections:

- **Click any section header** to expand or collapse it
- **All sections start collapsed** by default
- **Confidence badge shows** in the header without expanding
- **Multiple sections can be open** simultaneously

This keeps the interface clean while allowing you to drill into specific details.

---

## When Enrichment Data is Available

Enrichment data is computed automatically during event processing. Not all events will have all enrichment types:

| Detection Type | Available Enrichment                             |
| -------------- | ------------------------------------------------ |
| **Vehicle**    | Vehicle type, color, damage, license plate       |
| **Person**     | Clothing, action, carrying items, security flags |
| **Animal**     | Pet type, breed (if identifiable)                |
| **All**        | Weather conditions, image quality                |

If no enrichment data is available for an event, the AI Enrichment Analysis panel will not appear.

---

## How Enrichment Affects Risk Scores

The enrichment data directly influences the event's risk score:

**Factors that increase risk:**

- Suspicious attire (face coverings, all-dark at night)
- High-security vehicle damage (broken glass, broken lights)
- Poor image quality (possible camera tampering)
- Violence detection (when multiple people are present)

**Factors that decrease risk:**

- Confirmed household pets
- Service uniforms (delivery drivers, maintenance workers)
- Commercial vehicles (during daytime)

This helps the system provide more accurate risk assessments based on context, not just the presence of a person or vehicle.

---

## Data Retention

AI enrichment data is stored with the detection record and follows the same retention policy as events:

- **Default retention:** 30 days
- **Stored with:** The detection in the database
- **Exportable:** Yes, included in event exports

---

## Next Steps

- [Understanding Alerts](understanding-alerts.md) - How enrichment affects risk levels
- [Dashboard Settings](dashboard-settings.md) - Configure AI processing options

---

## See Also

- [Dashboard Basics](dashboard-basics.md) - Main dashboard overview
- [Viewing Events](viewing-events.md) - Event timeline and details
- [AI Pipeline Overview](../architecture/ai-pipeline.md) - Technical documentation on the enrichment pipeline

---

[Back to User Hub](../user-hub.md)

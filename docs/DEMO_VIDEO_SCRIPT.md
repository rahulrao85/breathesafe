# BreatheSafe — 2-Minute Demo Video Script

> Total runtime: 2:00. Read off this sheet while you record. Each
> segment has a hard time cap; rehearse once before recording.
> Resolution: 1920x1080. Audio: voice over screen capture.

---

## 0:00 - 0:15 — The hook (15s)

| Visual | Voice |
|---|---|
| Cold open. Black screen. Text fades in: "I have sleep apnea. I got diagnosed because I had access. 100 million Indians haven't been." | "I have sleep apnea. I got diagnosed because I had access to a clinic, a device, and a specialist. About 100 million Indians haven't. They live with the symptoms every night, and the system has no idea where to look for them." |
| Cut to: app open, scroll from top | "BreatheSafe is a district-level public-health intelligence layer for sleep apnea awareness in India. It is not a personal tracker. It is a way to find the places the system has missed." |

## 0:15 - 0:35 — The map (20s)

| Visual | Voice |
|---|---|
| Land on the Looker Studio dashboard. Hover India. Bubble map with high-risk red and low-awareness teal. | "We joined five public datasets — NFHS-5, Census, CPCB air quality, Google Trends awareness, and STOP-BANG-derived risk weights — in a single BigQuery view. Here it is as a heatmap." |
| Zoom into Uttar Pradesh. Five red bubbles appear. | "The red dots are high-risk districts. The size of the bubble is the estimated number of undiagnosed people." |
| Hover Delhi NCR. | "Delhi NCR is the textbook high-risk + high-awareness story. The interesting story is what Delhi is NOT telling us about — that's the desert." |

## 0:35 - 1:00 — Agent demo (25s)

| Visual | Voice |
|---|---|
| Back to the BreatheSafe app. Click the first fixed-prompt button: "Top 5 districts in Uttar Pradesh for OSA camps". | "Ask the agent where to focus first." |
| Wait ~2s. The agent card populates with a Markdown table (Kanpur Nagar, Meerut, Agra, Lucknow, Varanasi) and driving factors. | "It pulls a ranked list straight from BigQuery: Kanpur Nagar, Meerut, Agra, Lucknow, Varanasi. Notice the driving factors — PM2.5 over 120, obesity over 20 percent, hypertension over 13 percent." |
| Scroll down inside the agent card to show the "Sources cited" block. | "Every answer is grounded in the data, and it cites the medical literature. STOP-BANG, the WHO South-Asian BMI threshold, the Sharma et al. prevalence study." |

## 1:00 - 1:25 — Multimodal demo (25s)

| Visual | Voice |
|---|---|
| Scroll to the multimodal upload section. Drag in a screenshot of a Delhi pollution headline. | "Now the multimodal demo. This is the kind of input a public health officer might see — a newspaper headline about Delhi air pollution." |
| Click "Analyze image". Wait ~2s. Risk impact card appears with: location = Delhi NCR, matched district = Central Delhi, risk = 0.64, awareness gap = 0.08. | "Vertex AI Vision reads it — location, topic, key signals. The agent cross-references BigQuery. Central Delhi shows up: risk score 0.64, awareness already high. The recommendation is not 'screen more here' — it's 'screen where the awareness gap is the widest'." |

## 1:25 - 1:45 — Architecture (20s)

| Visual | Voice |
|---|---|
| Cut to the deck, slide 8 (architecture). Or screen-capture the architecture diagram block in the SPA. | "Under the hood: Cloud Storage holds the raw CSVs. BigQuery joins them in one view. Vertex AI runs the agent with three tools — a BigQuery tool, a RAG tool over medical guidelines, and a Vision tool. Cloud Run serves the app. Looker Studio gives you the open dashboard." |
| Briefly highlight each layer. | "One container. One agent. Five public datasets. One question: where should India screen first?" |

## 1:45 - 2:00 — Close (15s)

| Visual | Voice |
|---|---|
| Back to the SPA. Final shot: KPI strip + district table + footer disclaimer. | "BreatheSafe is screening-prioritization, not medical diagnosis. The risk scores are population estimates. They do not predict any individual's OSA. If you're concerned about your own sleep, see a qualified physician." |
| Fade to title card: "BreatheSafe. Five public datasets. One warehouse. One question." | "BreatheSafe." |
| Hold for 1s. End. | — |

---

## Recording checklist

- [ ] Window resized to 1920x1080 (or 1280x720 if your recorder struggles)
- [ ] Mouse cursor visible
- [ ] No notifications from Teams / Outlook / etc. during the recording
- [ ] DevTools closed
- [ ] All browser tabs other than BreatheSafe closed
- [ ] Network on a stable connection (no hot-spot drops)
- [ ] Practice run completed once end-to-end
- [ ] Audio level check: voice clear, no keyboard clacking

## Re-record triggers

- Audio cuts out or sounds muffled → re-record the whole segment
- Agent response is the deterministic composer (no Vertex AI feel) →
  check that the Cloud Run runtime SA has `roles/aiplatform.user` on
  the project; if it is granted and the composer is still deterministic,
  the `tools_called` block will tell you which tools ran
- Multimodal demo cross-reference shows no matched district → you used
  an image with a location not in the dataset; swap to the bundled
  Delhi pollution sample
- Cold start > 4s on first request → set `--min-instances=1` and retry

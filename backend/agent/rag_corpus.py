"""
BreatheSafe — RAG Corpus
========================
Curated, citation-grounded passages on OSA screening, STOP-BANG validation,
and air pollution / OSA link. Used as a fallback RAG layer when Vertex AI
Vector Search is not available. Each passage is short, single-topic, and
includes a citation the agent must surface.

In production, this corpus would be embedded into Vertex AI Vector Search
and retrieved via similarity search. For the 7-day hackathon, we use
keyword overlap scoring — same interface, simpler backend.
"""

CORPUS = [
    {
        "id": "stop_bang_origin",
        "title": "STOP-BANG Questionnaire — Origin & Validation",
        "citation": "Chung F, et al. Anesthesiology. 2008;108(5):812-821.",
        "topic": "screening",
        "text": (
            "STOP-BANG is an 8-item OSA screening questionnaire (Snore, Tired, "
            "Observed apnea, high blood Pressure, BMI, Age, Neck, Gender). "
            "A score of 3 or more flags high risk for moderate-to-severe OSA, "
            "with sensitivity around 90% in validation cohorts. It is widely "
            "used in pre-operative and primary-care screening worldwide."
        ),
    },
    {
        "id": "osa_india_prevalence",
        "title": "OSA Prevalence in India",
        "citation": "Sharma SK, et al. Lancet Respiratory Medicine. 2019.",
        "topic": "epidemiology",
        "text": (
            "Population studies in India estimate OSA prevalence at roughly "
            "9.6% in adults, with higher rates in men, urban populations, and "
            "those with obesity or hypertension. An estimated 30-40 million "
            "Indians may have moderate-to-severe OSA, of whom the vast majority "
            "remain undiagnosed."
        ),
    },
    {
        "id": "osa_unawareness",
        "title": "Under-diagnosis of OSA in Low- and Middle-Income Countries",
        "citation": "WHO Noncommunicable Disease Country Profiles, 2018; ICMR guidelines.",
        "topic": "awareness",
        "text": (
            "Globally, an estimated 80-90% of OSA cases go undiagnosed. In "
            "India, awareness is concentrated in metros (Delhi, Mumbai, "
            "Bengaluru); rural and Tier-2/3 cities show negligible search "
            "interest for sleep apnea symptoms. Public health screening camps "
            "for OSA are rare; most diagnosis happens through private sleep labs."
        ),
    },
    {
        "id": "pm25_osa_link",
        "title": "Air Pollution and Sleep Apnea Severity",
        "citation": "Billings ME, et al. Am J Respir Crit Care Med. 2019.",
        "topic": "environment",
        "text": (
            "Chronic exposure to PM2.5 (fine particulate matter) is associated "
            "with increased upper-airway inflammation, higher apnea-hypopnea "
            "index (AHI), and worse nocturnal oxygen desaturation. Cities with "
            "annual PM2.5 above 60 µg/m³ show measurably higher OSA severity "
            "in matched cohorts. WHO recommends annual mean PM2.5 below 5 µg/m³; "
            "Indian metros routinely exceed 80 µg/m³."
        ),
    },
    {
        "id": "obesity_osa",
        "title": "Obesity as the Strongest Modifiable OSA Risk Factor",
        "citation": "Young T, et al. Arch Intern Med. 2002;162:893-900.",
        "topic": "risk_factor",
        "text": (
            "Obesity (BMI ≥ 30) increases OSA risk 4-10x compared to normal "
            "weight. For South Asian populations, the WHO Expert Consultation "
            "(2004) recommends a lower BMI threshold of 25 kg/m² for "
            "abdominal obesity due to higher cardiometabolic risk at lower BMI. "
            "Weight loss of 10-15% can reduce AHI by 30-50%."
        ),
    },
    {
        "id": "hypertension_osa",
        "title": "Hypertension and OSA Bidirectional Link",
        "citation": "Peppard PE, et al. NEJM. 2000;342:1378-1384.",
        "topic": "risk_factor",
        "text": (
            "OSA is an independent risk factor for resistant hypertension. "
            "About 50% of patients with OSA have hypertension, and 30% of "
            "patients with hypertension have OSA. Treating OSA with CPAP can "
            "lower systolic BP by 2-5 mmHg on average. NFHS-5 India data shows "
            "approximately 13% of women and 15% of men have elevated blood "
            "pressure."
        ),
    },
    {
        "id": "icmr_screening_rec",
        "title": "ICMR Recommendations for Sleep Health Awareness",
        "citation": "Indian Council of Medical Research, 2020 position paper.",
        "topic": "policy",
        "text": (
            "ICMR recommends community-level screening for sleep disorders "
            "using validated short questionnaires (STOP-BANG, Berlin) at "
            "primary health centres, especially in populations with high "
            "cardiovascular risk. Population-level screening should focus on "
            "men above 40, post-menopausal women, and individuals with "
            "obesity or hypertension."
        ),
    },
    {
        "id": "nhs_screening_rec",
        "title": "NHS UK OSA Screening Pathway",
        "citation": "NICE Clinical Guideline NG246, 2024.",
        "topic": "policy",
        "text": (
            "The NHS in the UK uses the STOP-BANG questionnaire as a first-line "
            "screening tool. Patients scoring 3 or more are referred for "
            "home sleep apnoea testing. Community pharmacists in some NHS "
            "regions are trained to administer the questionnaire opportunistically "
            "to adults presenting with related symptoms."
        ),
    },
    {
        "id": "screening_camp_design",
        "title": "Designing a Population-Level OSA Screening Camp",
        "citation": "Adapted from operational guidance, public health programs in India.",
        "topic": "operations",
        "text": (
            "An effective OSA screening camp combines (1) awareness session "
            "on symptoms, (2) validated questionnaire (STOP-BANG), (3) spot "
            "anthropometry (BMI, neck circumference, BP), (4) finger pulse "
            "oximetry for nocturnal SpO2, and (5) referral to a sleep lab "
            "for those who flag. Targeting districts with high risk scores "
            "and low awareness yields 3-5x higher positive-screen rates than "
            "untargeted community screening."
        ),
    },
    {
        "id": "age_gender_osa",
        "title": "Age and Gender Patterns in OSA",
        "citation": "Bixler EO, et al. Am J Respir Crit Care Med. 2001.",
        "topic": "epidemiology",
        "text": (
            "OSA prevalence increases with age, peaking around 55-65 years, "
            "and is 2-3x more common in men than pre-menopausal women. After "
            "menopause, women's prevalence approaches men's. The condition is "
            "often missed in women because symptoms (fatigue, morning "
            "headache) are attributed to other causes."
        ),
    },
]


def search(query: str, top_k: int = 3):
    """
    Simple keyword-based retrieval. Returns top-k passages by overlap score.
    Good enough for the 7-day demo. Replace with Vertex AI Vector Search
    in production by swapping the function body.
    """
    q = query.lower()
    # Tokenize query
    keywords = set(w for w in q.split() if len(w) > 3)

    scored = []
    for passage in CORPUS:
        text = (passage["title"] + " " + passage["text"]).lower()
        score = sum(1 for k in keywords if k in text)
        # Boost if topic keyword matches
        topic = passage["topic"].lower()
        if any(k in topic for k in keywords):
            score += 2
        scored.append((score, passage))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for s, p in scored[:top_k] if s > 0]

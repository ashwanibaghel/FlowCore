import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from backend.app.config import Settings


class ContentGenerationService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate_daily_content(
        self,
        business_name: str,
        niche: str,
        target_audience: str,
        brand_tone: str,
        content_mode: str,
        cta: str,
        previous_posts: list[str],
        engagement_history: dict[str, Any],
        trend_keywords: list[str],
    ) -> dict[str, Any]:
        if not self.settings.openrouter_api_key:
            return self._fallback_content(business_name, niche, target_audience, cta, content_mode)

        is_carousel = content_mode.lower() in {"carousel", "story_carousel", "poster_story"}
        prompt = (
            self._build_carousel_prompt(cta=cta, trend_keywords=trend_keywords)
            if is_carousel
            else self._build_prompt(
                business_name=business_name,
                niche=niche,
                target_audience=target_audience,
                brand_tone=brand_tone,
                content_mode=content_mode,
                cta=cta,
                previous_posts=previous_posts,
                engagement_history=engagement_history,
                trend_keywords=trend_keywords,
            )
        )
        json_body = {
            "model": self.settings.openrouter_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a senior social media strategist and copywriter. "
                        "Return only strict JSON. No markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.75,
        }
        if not is_carousel:
            json_body["response_format"] = {"type": "json_object"}
        try:
            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                    "HTTP-Referer": self.settings.openrouter_site_url,
                    "X-Title": self.settings.openrouter_app_name,
                },
                json=json_body,
                timeout=90,
            )
            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(raw)
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
            print(f"AI content generation unavailable; using fallback content. Reason: {exc}")
            return self._sanitize(
                self._normalize(
                    self._fallback_content(business_name, niche, target_audience, cta, content_mode),
                    business_name,
                    niche,
                    target_audience,
                    cta,
                    content_mode,
                )
            )
        if is_carousel and isinstance(parsed, list):
            parsed = self._carousel_array_to_content(parsed, cta)
        return self._sanitize(
            self._normalize(parsed, business_name, niche, target_audience, cta, content_mode)
        )

    def _build_carousel_prompt(self, cta: str, trend_keywords: list[str]) -> str:
        return f"""
You are an expert copywriter creating highly viral Instagram Reels/carousel-video scripts for "ServiZephyr", a premium B2B SaaS platform for restaurants.

CORE PRODUCT CONTEXT:
ServiZephyr gives absolute operational control to restaurant/cafe owners: Online/WhatsApp ordering, Smart Dine-in with seat occupancy, Digital Khata/Borrowers management, Smart Billing, Analytics, waiting management, staff workflow, and delivery controls.
Tagline: "Business, Customer & Control - All Yours."

STRICT RULES:
1. Tone: Deeply relatable Hinglish. Emotional, sharp, focused entirely on restaurant owner daily pain points/stress.
2. Content Restriction: Never mention third-party aggregators, marketplaces, POS tools, or competitors by name. Use generic terms like "delivery portals" or "third-party apps".
3. Structure: Exactly 7 slides. Each slide must last 3 seconds. Total 21 seconds.
4. Slide 7 must be tag "CTA", headline "DM 'RESTAURANT' Now!" and subtext "Visit https://www.servizephyr.com or DM us to bring restaurant control into one place."
5. Output Format: Return ONLY a valid JSON array. No conversational text before or after JSON.

TREND/ANGLE KEYWORDS:
{", ".join(trend_keywords)}

JSON STRUCTURE:
[
  {{
    "slide": 1,
    "tag": "HOOK",
    "headline": "Max 4-5 words, high-impact Hinglish",
    "subtext": "Relatable question focusing on chaos/pain",
    "pexels_query": "Exact visual search term for Pexels API"
  }}
]
""".strip()

    def _carousel_array_to_content(self, slides: list[dict[str, Any]], cta: str) -> dict[str, Any]:
        normalized_slides = []
        roles = {
            "HOOK": "hook",
            "STORY": "story",
            "CONFLICT": "conflict",
            "EMOTION": "emotion",
            "SOLUTION": "solution",
            "BENEFIT": "benefit",
            "CTA": "cta",
        }
        for index, slide in enumerate(slides[:7], start=1):
            tag = str(slide.get("tag") or "STORY").upper()
            normalized_slides.append(
                {
                    "slide_number": int(slide.get("slide") or index),
                    "role": roles.get(tag, tag.lower()),
                    "tag": tag,
                    "headline": str(slide.get("headline") or "Restaurant Reality"),
                    "body": str(slide.get("subtext") or ""),
                    "visual_direction": str(slide.get("pexels_query") or "restaurant owner working"),
                    "pexels_query": str(slide.get("pexels_query") or "restaurant owner working"),
                    "emotion": self._emotion_for_tag(tag),
                }
            )
        while len(normalized_slides) < 7:
            fallback = self._restaurant_carousel_fallback(cta)["carousel"]["slides"][len(normalized_slides)]
            normalized_slides.append(fallback)
        title = normalized_slides[0]["headline"]
        return {
            "topic": {
                "reel_topic": title,
                "hook": normalized_slides[0]["headline"],
                "audience_pain_point": normalized_slides[0]["body"],
                "cta": cta,
                "idea_summary": "A 7-slide Restaurant Reality Story for ServiZephyr Restaurant.",
            },
            "script": {
                "short_reel_script": " | ".join(f"{s['headline']}: {s['body']}" for s in normalized_slides),
                "voiceover_script": "",
                "subtitles": [s["headline"] for s in normalized_slides],
                "scenes": [],
            },
            "caption": {
                "instagram_caption": self._restaurant_caption(title, cta),
                "hashtags": [
                    "#ServiZephyr",
                    "#RestaurantSoftware",
                    "#RestaurantOwner",
                    "#RestaurantManagement",
                    "#CafeBusiness",
                    "#FoodBusiness",
                    "#BillingSoftware",
                    "#BusinessControl",
                ],
                "cta": cta,
                "engagement_prompt": "Aapke restaurant me sabse bada daily chaos kya hai?",
            },
            "meme": {},
            "carousel": {"title": title, "slides": normalized_slides},
            "video_prompts": {"style": "Premium restaurant story carousel video.", "prompts": []},
        }

    def _emotion_for_tag(self, tag: str) -> str:
        return {
            "HOOK": "stress",
            "STORY": "confusion",
            "CONFLICT": "frustration",
            "EMOTION": "stress",
            "SOLUTION": "relief",
            "BENEFIT": "control",
            "CTA": "confidence",
        }.get(tag, "stress")

    def _restaurant_caption(self, title: str, cta: str) -> str:
        return (
            f"{title} - restaurant chaos ko control me lana hai? "
            "ServiZephyr helps simplify orders, billing, waiting, customers and staff workflows. "
            f"Visit https://www.servizephyr.com or {cta}."
        )

    def _build_prompt(
        self,
        business_name: str,
        niche: str,
        target_audience: str,
        brand_tone: str,
        content_mode: str,
        cta: str,
        previous_posts: list[str],
        engagement_history: dict[str, Any],
        trend_keywords: list[str],
    ) -> str:
        return json.dumps(
            {
                "task": "Generate one daily Instagram Reel content package for an automation platform MVP.",
                "business_name": business_name,
                "niche": niche,
                "target_audience": target_audience,
                "brand_tone": brand_tone,
                "content_mode": content_mode,
                "product_brief": self._servizephyr_restaurant_brief(),
                "creative_direction": self._creative_direction(content_mode),
                "preferred_cta": cta,
                "previous_posts": previous_posts[-10:],
                "engagement_history": engagement_history,
                "trend_keywords": trend_keywords,
                "output_schema": {
                    "topic": {
                        "reel_topic": "string",
                        "hook": "string",
                        "audience_pain_point": "string",
                        "cta": "string",
                        "idea_summary": "string",
                    },
                    "script": {
                        "short_reel_script": "string",
                        "voiceover_script": "string",
                        "subtitles": ["5-8 short subtitle lines"],
                        "scenes": [
                            {
                                "scene_number": "integer",
                                "visual": "string",
                                "on_screen_text": "string",
                                "voiceover": "string",
                            }
                        ],
                    },
                    "caption": {
                        "instagram_caption": "string",
                        "hashtags": ["8-15 hashtags"],
                        "cta": "string",
                        "engagement_prompt": "string",
                    },
                    "meme": {
                        "top_text": "short setup text for a meme template",
                        "bottom_text": "short punchline that naturally points to ServiZephyr Restaurant",
                        "template_hint": "one short phrase like distracted boyfriend, drake, two buttons, expanding brain, waiting skeleton",
                        "frames": [
                            {
                                "top_text": "very short meme setup",
                                "bottom_text": "very short punchline",
                                "template_hint": "drake, two buttons, expanding brain, change my mind, waiting skeleton",
                            }
                        ],
                    },
                    "carousel": {
                        "title": "short story title",
                        "slides": [
                            {
                                "slide_number": "integer",
                                "role": "hook, story, conflict, emotion, solution, benefit, cta",
                                "headline": "short punchy headline",
                                "body": "1-2 short lines",
                                "visual_direction": "restaurant visual direction",
                                "emotion": "stress, confusion, relief, control, etc",
                            }
                        ],
                    },
                    "video_prompts": {
                        "style": "string",
                        "prompts": ["one prompt per scene for an AI video generation tool"],
                    },
                },
                "rules": [
                    "Keep the reel 12-25 seconds.",
                    "Use concrete restaurant owner, manager, cashier, waiter, chef, or customer pain points.",
                    "Show the pain first, then present ServiZephyr Restaurant as the solution.",
                    "Do not mention, compare with, or hint at any third-party brand, app, marketplace, delivery platform, POS, or competitor by name.",
                    "Do not write generic software jargon; make the situation instantly relatable for Indian restaurants, cafes, dhabas, QSRs, and cloud kitchens.",
                    "For meme mode, make the script funny, punchy, Hinglish-friendly, and built around a clear setup-punchline-solution structure.",
                    "For carousel mode, create 7 slides: hook, setup, conflict, emotional owner pain, solution shift, operational benefits, final brand CTA.",
                    "ServiZephyr Restaurant must feel like the natural fix, not a forced advertisement.",
                    "Avoid fake claims and guaranteed results.",
                    "Make subtitles short enough for mobile screens.",
                ],
            },
            ensure_ascii=True,
        )

    def _normalize(
        self,
        content: dict[str, Any],
        business_name: str,
        niche: str,
        target_audience: str,
        cta: str,
        content_mode: str,
    ) -> dict[str, Any]:
        fallback = self._fallback_content(business_name, niche, target_audience, cta, content_mode)
        for key, value in fallback.items():
            content.setdefault(key, value)
        content["topic"] = {**fallback["topic"], **content.get("topic", {})}
        content["script"] = {**fallback["script"], **content.get("script", {})}
        content["caption"] = {**fallback["caption"], **content.get("caption", {})}
        content["meme"] = {**fallback.get("meme", {}), **content.get("meme", {})}
        content["carousel"] = {**fallback.get("carousel", {}), **content.get("carousel", {})}
        content["video_prompts"] = {**fallback["video_prompts"], **content.get("video_prompts", {})}
        if not content["script"].get("scenes"):
            content["script"]["scenes"] = fallback["script"]["scenes"]
        if not content["script"].get("subtitles"):
            content["script"]["subtitles"] = [scene["on_screen_text"] for scene in content["script"]["scenes"]]
        return content

    def _fallback_content(
        self,
        business_name: str,
        niche: str,
        target_audience: str,
        cta: str,
        content_mode: str = "meme",
    ) -> dict[str, Any]:
        if content_mode.lower() in {"carousel", "story_carousel", "poster_story"}:
            return self._restaurant_carousel_fallback(cta)
        if content_mode.lower() == "meme" or "restaurant" in niche.lower():
            return self._restaurant_meme_fallback(cta)
        return {
            "topic": {
                "reel_topic": "Stop losing hours on repetitive business follow-ups",
                "hook": "Your team is not slow. Your workflow is overloaded.",
                "audience_pain_point": f"{target_audience} spend too much time on manual replies and content tasks.",
                "cta": cta,
                "idea_summary": f"Show how {business_name} automates repeat work for {niche}.",
            },
            "script": {
                "short_reel_script": (
                    "Your team is not slow. Your workflow is overloaded. "
                    "Every manual reply, reminder, and content task steals time from real customers. "
                    "FlowCore builds AI automations that handle the repeat work while your team focuses on sales."
                ),
                "voiceover_script": (
                    "Your team is not slow. Your workflow is overloaded. "
                    "Automate follow-ups, reminders, and daily content so your business can move faster."
                ),
                "subtitles": [
                    "Your team is not slow.",
                    "Your workflow is overloaded.",
                    "Manual replies eat your day.",
                    "Daily content gets delayed.",
                    "AI can handle the repeat work.",
                    cta,
                ],
                "scenes": [
                    {
                        "scene_number": 1,
                        "visual": "Busy owner checking messages",
                        "on_screen_text": "Your team is not slow.",
                        "voiceover": "Your team is not slow.",
                    },
                    {
                        "scene_number": 2,
                        "visual": "Tasks stacking on a dashboard",
                        "on_screen_text": "Your workflow is overloaded.",
                        "voiceover": "Your workflow is overloaded.",
                    },
                    {
                        "scene_number": 3,
                        "visual": "Automated replies and reminders",
                        "on_screen_text": "Automate the repeat work.",
                        "voiceover": "AI can handle repetitive replies, reminders, and daily content.",
                    },
                    {
                        "scene_number": 4,
                        "visual": "Business owner focused on customer",
                        "on_screen_text": cta,
                        "voiceover": cta,
                    },
                ],
            },
            "caption": {
                "instagram_caption": (
                    "Repetitive work quietly drains your business every day. "
                    "Automations can handle follow-ups, reminders, and content workflows while your team focuses on customers."
                ),
                "hashtags": [
                    "#automation",
                    "#aiautomation",
                    "#smallbusiness",
                    "#businessgrowth",
                    "#workflowautomation",
                    "#instagrammarketing",
                    "#flowcore",
                    "#aitools",
                ],
                "cta": cta,
                "engagement_prompt": "What task would you automate first?",
            },
            "meme": {
                "top_text": "Manual follow-ups all day",
                "bottom_text": "FlowCore automates the repeat work",
                "template_hint": "drake hotline bling",
            },
            "carousel": {
                "title": "Manual Work Overload",
                "slides": [],
            },
            "video_prompts": {
                "style": "Modern vertical business reel, clean UI overlays, high contrast, energetic pacing.",
                "prompts": [
                    "A small business owner overwhelmed by message notifications, vertical 9:16, modern office.",
                    "A clean automation dashboard organizing customer follow-ups, vertical 9:16.",
                    "AI workflow nodes sending reminders and content tasks automatically, vertical 9:16.",
                    "Confident business owner serving a customer while automations run in the background, vertical 9:16.",
                ],
            },
        }

    def _servizephyr_restaurant_brief(self) -> dict[str, Any]:
        return {
            "name": "ServiZephyr Restaurant",
            "tagline": "Business, Customer & Control — All Yours.",
            "audience": "restaurants, cafes, dhabas, QSRs, cloud kitchens, and local food businesses",
            "positioning": (
                "A restaurant technology platform that helps owners manage online ordering, pickup, "
                "dine-in, waiting queues, billing, customer records, staff workflows, analytics, "
                "delivery controls, multi-branch operations, and borrower/khata records from a flexible system."
            ),
            "features": [
                "WhatsApp-based online ordering flow with no separate customer app installation",
                "pickup and delivery orders",
                "live order status tracking",
                "dine-in QR ordering and seat occupancy management",
                "digital waiting queue, token generation, and seating workflow",
                "smart billing with thermal printer, custom taxes, charges, and GST settings",
                "coupon and offer campaigns",
                "customer history, repeat customer insights, top customers, and item insights",
                "delivery range, charges, blocked areas, and custom rules",
                "staff roles for waiter, chef, cashier, manager, and owner",
                "multi-branch management",
                "borrower/khata style pending payment tracking",
            ],
            "core_message": "Restaurant ka business, customers, orders, billing, staff, aur control owner ke haath me.",
        }

    def _creative_direction(self, content_mode: str) -> dict[str, str]:
        if content_mode.lower() in {"carousel", "story_carousel", "poster_story"}:
            return {
                "format": "Instagram carousel story",
                "language": "Hinglish with simple English where useful",
                "tone": "relatable, emotional, funny, clean, premium",
                "structure": "hook -> restaurant chaos story -> owner emotion -> ServiZephyr Restaurant shift -> benefits -> CTA",
            }
        if content_mode.lower() == "meme":
            return {
                "format": "short meme reel",
                "language": "Hinglish with simple English where useful",
                "tone": "funny, relatable, slightly dramatic, never insulting",
                "structure": "chaos setup -> funny punchline -> ServiZephyr Restaurant solution -> CTA",
            }
        return {
            "format": "short educational reel",
            "language": "Hinglish or English",
            "tone": "clear, practical, confident",
            "structure": "problem -> insight -> solution -> CTA",
        }

    def _restaurant_carousel_fallback(self, cta: str) -> dict[str, Any]:
        story = self._select_restaurant_carousel_story()
        slides = [
            {
                "slide_number": index,
                "role": role,
                "headline": headline,
                "body": body,
                "visual_direction": visual,
                "emotion": emotion,
            }
            for index, (role, headline, body, visual, emotion) in enumerate(story["slides"], start=1)
        ]
        return {
            "topic": {
                "reel_topic": story["title"],
                "hook": story["hook"],
                "audience_pain_point": story["pain_point"],
                "cta": cta,
                "idea_summary": story["idea_summary"],
            },
            "script": {
                "short_reel_script": "A 7-slide carousel story showing restaurant chaos and the shift to ServiZephyr.",
                "voiceover_script": "",
                "subtitles": [slide["headline"] for slide in slides],
                "scenes": [],
            },
            "caption": {
                "instagram_caption": (
                    f"{story['caption']} "
                    "ServiZephyr helps bring orders, billing, waiting, customers, staff workflow, and control into one system. "
                    "Visit https://www.servizephyr.com or DM us the word RESTAURANT."
                ),
                "hashtags": [
                    "#ServiZephyr",
                    "#RestaurantSoftware",
                    "#RestaurantOwner",
                    "#CafeBusiness",
                    "#FoodBusiness",
                    "#RestaurantManagement",
                    "#BillingSoftware",
                    "#DineIn",
                    "#RestaurantLife",
                    "#BusinessControl",
                ],
                "cta": cta,
                "engagement_prompt": "Aapke restaurant me peak hour ka sabse bada chaos kya hota hai?",
            },
            "meme": {
                "top_text": story["title"],
                "bottom_text": "Control chahiye, daily drama nahi",
                "template_hint": "drake",
            },
            "carousel": {
                "title": story["title"],
                "slides": slides,
            },
            "video_prompts": {
                "style": "Premium restaurant story carousel, modern brand design, emotional but clean.",
                "prompts": [slide["visual_direction"] for slide in slides],
            },
        }

    def _select_restaurant_carousel_story(self) -> dict[str, Any]:
        stories = self._restaurant_carousel_story_bank()
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        slot = 0
        if 6 <= now.hour < 13:
            slot = 1
        elif now.hour >= 13:
            slot = 2
        index = ((now.toordinal() * 3) + slot) % len(stories)
        return stories[index]

    def _restaurant_carousel_story_bank(self) -> list[dict[str, Any]]:
        cta_slide = (
            "cta",
            "DM 'RESTAURANT' Now!",
            "Visit https://www.servizephyr.com or message us to bring control into one place.",
            "minimal brand end card no photo",
            "confidence",
        )
        return [
            {
                "title": "Peak Hour ka Darr",
                "hook": "7:30 PM. Restaurant full. Aur system full confused.",
                "pain_point": "Peak hour me scattered orders, billing, waiting, aur staff updates owner ka control tod dete hain.",
                "idea_summary": "Peak-hour chaos turns into one controlled restaurant workflow.",
                "caption": "Peak hour ka chaos har restaurant owner samajhta hai.",
                "slides": [
                    ("hook", "Peak Hour ka Darr", "7:30 PM. Restaurant full. Owner already alert mode me.", "crowded restaurant evening rush", "anticipation"),
                    ("setup", "Table 4 ka order?", "Waiter: kitchen tak gaya hoga. Kitchen: kaunsa order?", "waiter confused near kitchen counter", "confusion"),
                    ("conflict", "Customer ka patience gaya", "Bhai mera order 40 min se kahan hai?", "customer waiting at table", "frustration"),
                    ("emotion", "Owner ka real stress", "Dine-in alag. Pickup alag. Billing alag. Waiting list alag.", "restaurant owner stressed at billing counter", "stress"),
                    ("solution", "Then they shifted", "ServiZephyr brought the workflow into one place.", "manager using tablet in restaurant", "relief"),
                    ("benefit", "Orders. Billing. Waiting.", "Tracking, staff roles, customers and control - all connected.", "restaurant pos terminal billing counter", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Bill Match Nahi Hua",
                "hook": "Counter close hua. Cash mismatch start.",
                "pain_point": "Manual billing aur scattered payments closing time par owner ko doubt me daal dete hain.",
                "idea_summary": "Billing mismatch stress becomes cleaner billing control.",
                "caption": "Closing time ka cash mismatch owner ka mood kharab kar deta hai.",
                "slides": [
                    ("hook", "Bill Match Nahi Hua", "Raat ko counter close. Cash aur bill total alag.", "restaurant cashier counting cash", "stress"),
                    ("setup", "Staff bole: pata nahi", "Kis order ka payment pending hai, kisi ko clear nahi.", "stressed cashier restaurant bill", "confusion"),
                    ("conflict", "Owner calculator pakde", "10 min ka closing kaam 45 min ka tension ban gaya.", "tired restaurant owner calculator", "frustration"),
                    ("emotion", "Daily ka same scene", "Business chal raha hai, par control feel nahi ho raha.", "restaurant owner holding head", "stress"),
                    ("solution", "ServiZephyr entry", "Billing, order status aur payment records ek flow me.", "restaurant billing software pos", "relief"),
                    ("benefit", "Closing becomes clear", "Owner ko pata: kya paid, kya pending, kya delivered.", "pos terminal receipt restaurant", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Waiter Confusion Mode",
                "hook": "Table ka order kisne liya?",
                "pain_point": "Staff roles clear na ho to orders kitchen tak late ya wrong pahuchte hain.",
                "idea_summary": "Waiter confusion becomes role-based order tracking.",
                "caption": "Waiter confusion chhota issue lagta hai, par customer experience wahi se toot ta hai.",
                "slides": [
                    ("hook", "Waiter Confusion Mode", "Table 6 ka order kis waiter ne liya?", "busy restaurant waiter taking order", "confusion"),
                    ("setup", "Kitchen wait kar rahi", "Chef ready hai, par order slip missing hai.", "restaurant kitchen chefs waiting", "confusion"),
                    ("conflict", "Customer repeat kar raha", "Bhai order already diya tha na?", "customer talking to waiter restaurant", "frustration"),
                    ("emotion", "Owner beech me phas gaya", "Staff blame game. Customer ka mood down.", "restaurant manager stressed staff", "stress"),
                    ("solution", "One workflow helps", "ServiZephyr staff roles aur order tracking clear karta hai.", "manager tablet restaurant staff", "relief"),
                    ("benefit", "Order ka owner clear", "Kisne liya, status kya hai, kitchen me kya chal raha - sab visible.", "restaurant order management tablet", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Waiting Line Drama",
                "hook": "Table empty hai, par customer wait kar raha.",
                "pain_point": "Manual waiting list me seating opportunities miss hoti hain.",
                "idea_summary": "Waiting chaos becomes visible table control.",
                "caption": "Restaurant me waiting line manage karna bhi real business control hai.",
                "slides": [
                    ("hook", "Waiting Line Drama", "Bahaar line lagi hai. Andar table 2 empty hai.", "people waiting outside restaurant", "stress"),
                    ("setup", "Staff ko pata late", "Table clean ho gayi, par waiting list update nahi hui.", "restaurant staff cleaning table", "confusion"),
                    ("conflict", "Customer chala gaya", "Sir, 25 min wait bola tha. Ab dusri jagah ja rahe hain.", "customer leaving restaurant", "frustration"),
                    ("emotion", "Owner ko loss dikha", "Empty table ka matlab direct missed revenue.", "restaurant owner looking at empty tables", "stress"),
                    ("solution", "Waiting gets tracked", "ServiZephyr waiting aur seating flow ko visible karta hai.", "restaurant host tablet seating", "relief"),
                    ("benefit", "Seat faster. Serve better.", "Table, queue aur customer flow ek jagah control me.", "busy restaurant dining tables", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Pickup Order Missing",
                "hook": "Customer pickup ke liye aa gaya.",
                "pain_point": "Pickup orders manually track karne se kitchen aur counter sync nahi rahte.",
                "idea_summary": "Pickup order confusion becomes live status control.",
                "caption": "Pickup order ready nahi ho to customer ka trust instantly down hota hai.",
                "slides": [
                    ("hook", "Pickup Order Missing", "Customer counter par: order ready hai?", "restaurant takeaway counter customer", "stress"),
                    ("setup", "Kitchen: kaunsa pickup?", "Counter par naam hai, kitchen board par nahi.", "restaurant kitchen takeaway orders", "confusion"),
                    ("conflict", "Customer wait kar raha", "Bas 5 min bolke 20 min ho gaye.", "customer waiting takeaway restaurant", "frustration"),
                    ("emotion", "Owner damage control", "Sorry bolna padta hai, par system same rehta hai.", "restaurant owner apologizing customer", "stress"),
                    ("solution", "Status becomes live", "ServiZephyr pickup orders ko status ke sath track karta hai.", "restaurant order status tablet", "relief"),
                    ("benefit", "Ready means ready", "Order accepted, preparing, ready - counter aur kitchen synced.", "takeaway food bags restaurant counter", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Online Order Rush",
                "hook": "Phone ping, counter ring, kitchen swing.",
                "pain_point": "Online, phone, and counter orders scattered hone par kitchen overload hoti hai.",
                "idea_summary": "Order rush becomes one clear operations board.",
                "caption": "Online order rush me owner ko speed ke sath control bhi chahiye.",
                "slides": [
                    ("hook", "Online Order Rush", "Ek saath online, phone aur dine-in orders aa gaye.", "busy restaurant kitchen order rush", "stress"),
                    ("setup", "Kitchen overloaded", "Kaunsa order pehle? Kaunsa urgent? Sab mixed.", "chefs busy restaurant kitchen", "confusion"),
                    ("conflict", "Delay ka chain reaction", "Ek order late, teen customers angry.", "restaurant staff rushing orders", "frustration"),
                    ("emotion", "Owner ka pressure high", "Speed chahiye, par visibility zero.", "stressed restaurant manager kitchen", "stress"),
                    ("solution", "Orders in one view", "ServiZephyr orders ko organized flow me laata hai.", "restaurant tablet order dashboard", "relief"),
                    ("benefit", "Rush bhi manageable", "Kitchen, counter aur owner ek status dekhte hain.", "organized restaurant kitchen chefs", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Khata Ka Confusion",
                "hook": "Kal de denge, sir.",
                "pain_point": "Borrower/khata pending payments manual diary me lost ho jaate hain.",
                "idea_summary": "Khata confusion becomes trackable borrower control.",
                "caption": "Khata aur pending payments restaurant ke silent stress hote hain.",
                "slides": [
                    ("hook", "Khata Ka Confusion", "Regular customer: kal de denge, sir.", "small restaurant customer paying later", "confusion"),
                    ("setup", "Diary me entry hai?", "Staff: shayad likha tha. Owner: kis page par?", "restaurant owner notebook bill", "confusion"),
                    ("conflict", "Pending amount bhool gaya", "Chhote-chhote pending monthly bada number ban jate hain.", "restaurant bills notebook calculator", "frustration"),
                    ("emotion", "Trust bhi, tracking bhi", "Owner ko relation bhi sambhalna hai, payment bhi.", "restaurant owner stressed notebook", "stress"),
                    ("solution", "Digital khata helps", "ServiZephyr borrower records ko clear rakhne me help karta hai.", "restaurant tablet customer records", "relief"),
                    ("benefit", "Pending visible rahe", "Customer, amount aur history ek jagah.", "business owner tablet records cafe", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Repeat Customer Lost",
                "hook": "Regular customer ko bhi yaad nahi rakha.",
                "pain_point": "Customer history clear na ho to repeat business personalize nahi hota.",
                "idea_summary": "Customer memory becomes repeat customer insight.",
                "caption": "Repeat customers restaurant ki real asset hote hain.",
                "slides": [
                    ("hook", "Repeat Customer Lost", "Customer har Sunday aata hai. Staff ko naam tak yaad nahi.", "restaurant regular customer table", "confusion"),
                    ("setup", "Same order. Same table.", "Par system me koi history nahi.", "cafe customer ordering food", "confusion"),
                    ("conflict", "Personal touch missing", "Customer ko feel hota hai: main bas ek bill hun.", "restaurant customer disappointed", "frustration"),
                    ("emotion", "Owner ko pata hai value", "Loyal customer ko retain karna discount se zyada smart hai.", "restaurant owner talking customer", "stress"),
                    ("solution", "Customer history clear", "ServiZephyr customer records aur insights ko organize karta hai.", "restaurant manager tablet customer", "relief"),
                    ("benefit", "Repeat business stronger", "Top customers, history aur preferences owner ke control me.", "happy restaurant customer owner", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Offer Ka Overload",
                "hook": "Coupon diya, tracking bhool gaye.",
                "pain_point": "Offers/coupons manual hone par discount ka real impact track nahi hota.",
                "idea_summary": "Offer chaos becomes campaign control.",
                "caption": "Offer tabhi kaam karta hai jab owner ko uska impact dikhe.",
                "slides": [
                    ("hook", "Offer Ka Overload", "Weekend offer chala diya. Tracking kahan hai?", "restaurant discount sign counter", "confusion"),
                    ("setup", "Staff alag rule bata raha", "Kisi ne 10%, kisi ne free item apply kar diya.", "restaurant cashier coupon bill", "confusion"),
                    ("conflict", "Profit ka math missing", "Sale badhi ya sirf discount gaya?", "restaurant owner calculator bill", "frustration"),
                    ("emotion", "Owner unsure", "Marketing karna hai, par blind discount nahi.", "cafe owner stressed laptop", "stress"),
                    ("solution", "Campaign control", "ServiZephyr offers aur billing ko connected rakhta hai.", "restaurant pos coupon screen", "relief"),
                    ("benefit", "Offer with clarity", "Rules, billing aur customer response visible.", "restaurant owner checking tablet", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Kitchen Delay Panic",
                "hook": "Food ready hai ya nahi?",
                "pain_point": "Kitchen status invisible ho to staff guesswork se customer handle karta hai.",
                "idea_summary": "Kitchen delay panic becomes status visibility.",
                "caption": "Kitchen status clear ho to customer handling half easy ho jati hai.",
                "slides": [
                    ("hook", "Kitchen Delay Panic", "Waiter baar-baar kitchen me jhaank raha hai.", "waiter looking into restaurant kitchen", "stress"),
                    ("setup", "Chef busy hai", "Order list long hai, priority unclear hai.", "busy chef restaurant kitchen", "confusion"),
                    ("conflict", "Customer update maang raha", "Sir, aur kitna time lagega?", "customer asking waiter restaurant", "frustration"),
                    ("emotion", "Staff guess kar raha", "5 min bol diya. Actual me 15 min.", "stressed waiter restaurant", "stress"),
                    ("solution", "Live status view", "ServiZephyr kitchen status ko workflow me laata hai.", "restaurant kitchen order display", "relief"),
                    ("benefit", "Updates become honest", "Preparing, ready, served - team ko clear signal.", "organized kitchen restaurant chefs", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Staff Shift Confusion",
                "hook": "Shift change, details gone.",
                "pain_point": "Shift handover weak ho to pending orders and customer updates miss ho jaate hain.",
                "idea_summary": "Shift change confusion becomes shared workflow continuity.",
                "caption": "Restaurant me shift handover smooth nahi hua to chaos double ho jata hai.",
                "slides": [
                    ("hook", "Staff Shift Confusion", "Evening shift aayi. Pending orders ka context gaya.", "restaurant staff shift change", "confusion"),
                    ("setup", "Table 8 waiting", "New waiter ko pata hi nahi customer ne kya bola tha.", "waiter confused restaurant table", "confusion"),
                    ("conflict", "Customer repeat kar raha", "Maine pehle hi staff ko bola tha.", "angry customer restaurant waiter", "frustration"),
                    ("emotion", "Owner ko intervene karna", "Har handover me owner ko referee banna padta hai.", "restaurant manager stressed staff meeting", "stress"),
                    ("solution", "Shared workflow helps", "ServiZephyr roles, orders aur status ko connected rakhta hai.", "restaurant team tablet", "relief"),
                    ("benefit", "Shift changes smoother", "New staff ko live context milta hai.", "restaurant staff organized counter", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Table Turnover Slow",
                "hook": "Table khaali, revenue slow.",
                "pain_point": "Slow table turnover peak hours me revenue leak karta hai.",
                "idea_summary": "Table turnover becomes visible occupancy control.",
                "caption": "Restaurant me table turnover speed directly business impact karti hai.",
                "slides": [
                    ("hook", "Table Turnover Slow", "Customer nikal gaya. Table status update nahi hua.", "empty restaurant table after meal", "confusion"),
                    ("setup", "Waiting list stuck", "Bahaar customer wait kar raha, andar table idle.", "restaurant waiting customers", "stress"),
                    ("conflict", "Revenue leak silently", "Ek table delay, multiple orders miss.", "restaurant owner looking at tables", "frustration"),
                    ("emotion", "Owner notice late", "Busy hours me small delays big loss ban jate hain.", "stressed cafe owner dining area", "stress"),
                    ("solution", "Seat occupancy visible", "ServiZephyr dine-in aur table status track karne me help karta hai.", "restaurant seating tablet", "relief"),
                    ("benefit", "Turn tables smarter", "Occupied, cleaning, ready - flow clear.", "restaurant dining area staff", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Menu Item Sold Out",
                "hook": "Customer ne order diya. Item khatam.",
                "pain_point": "Menu availability sync na ho to wrong expectations create hoti hain.",
                "idea_summary": "Sold-out confusion becomes menu control.",
                "caption": "Item sold out update late ho to customer trust hurt hota hai.",
                "slides": [
                    ("hook", "Menu Item Sold Out", "Customer ne favourite item order kiya.", "restaurant menu customer ordering", "anticipation"),
                    ("setup", "Kitchen se jawab aaya", "Sir, ye item khatam ho gaya.", "chef restaurant kitchen talking", "confusion"),
                    ("conflict", "Customer disappointed", "Order lene se pehle batana tha na.", "disappointed restaurant customer", "frustration"),
                    ("emotion", "Staff awkward", "Replacement suggest karna padta hai, mood already down.", "waiter apologizing restaurant", "stress"),
                    ("solution", "Menu control matters", "ServiZephyr menu, orders aur availability ko organize karta hai.", "restaurant tablet menu", "relief"),
                    ("benefit", "Less awkward moments", "Available items clear, staff confident.", "happy waiter restaurant tablet", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Printer Drama",
                "hook": "Bill print nahi hua.",
                "pain_point": "Billing/printer confusion peak hour counter ko slow kar deta hai.",
                "idea_summary": "Counter printer drama becomes smoother billing workflow.",
                "caption": "Billing counter slow hua to poora restaurant line me aa jata hai.",
                "slides": [
                    ("hook", "Printer Drama", "Customer payment kar chuka. Bill print nahi hua.", "restaurant bill printer counter", "stress"),
                    ("setup", "Counter line badh gayi", "Ek bill issue, poori queue stuck.", "people waiting billing counter restaurant", "frustration"),
                    ("conflict", "Staff panic mode", "Reprint? Manual bill? Duplicate entry?", "cashier stressed pos restaurant", "confusion"),
                    ("emotion", "Owner ka patience test", "Small tech issue, big customer pressure.", "restaurant owner billing counter stressed", "stress"),
                    ("solution", "Billing workflow cleaner", "ServiZephyr billing flow ko structured rakhta hai.", "pos receipt restaurant billing", "relief"),
                    ("benefit", "Counter moves faster", "Bill, order aur payment details connected.", "restaurant cashier smiling pos", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Manager Not Updated",
                "hook": "Owner bahar, chaos andar.",
                "pain_point": "Owner ko live updates na milen to remote control impossible ho jata hai.",
                "idea_summary": "Owner visibility improves even when not at the restaurant.",
                "caption": "Restaurant owner har time counter par nahi ho sakta, par control chahiye.",
                "slides": [
                    ("hook", "Owner Bahar Hai", "Owner meeting me hai. Restaurant me rush start.", "restaurant owner phone outside cafe", "stress"),
                    ("setup", "Updates late aa rahe", "Kya sale hua? Kitni waiting? Kaunsa issue?", "business owner checking phone stressed", "confusion"),
                    ("conflict", "Decision delay", "Owner ko pata tab chalta hai jab problem badh chuki hoti hai.", "restaurant manager phone worried", "frustration"),
                    ("emotion", "Remote control missing", "Business owner ko real-time confidence chahiye.", "restaurant owner stressed phone", "stress"),
                    ("solution", "Visibility in one place", "ServiZephyr operations ko owner-friendly view me laata hai.", "restaurant dashboard tablet", "relief"),
                    ("benefit", "Owner stays informed", "Orders, billing, customers aur staff workflow clearer.", "restaurant owner smiling tablet", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Customer Complaint Loop",
                "hook": "Complaint aayi. Follow-up gaya.",
                "pain_point": "Complaint follow-up miss hone par customer trust weak hota hai.",
                "idea_summary": "Complaint chaos becomes trackable customer handling.",
                "caption": "Complaint handle karna sirf sorry bolna nahi, process bhi hai.",
                "slides": [
                    ("hook", "Complaint Loop", "Customer ne bola: last order cold tha.", "restaurant customer complaint waiter", "stress"),
                    ("setup", "Staff ne note kiya", "Par follow-up kahan track hua?", "waiter writing note restaurant", "confusion"),
                    ("conflict", "Same customer wapas nahi aaya", "Issue solve nahi hua, relation weak ho gaya.", "empty restaurant table customer", "frustration"),
                    ("emotion", "Owner ko regret", "Ek complaint ignore nahi, insight hoti hai.", "restaurant owner thinking counter", "stress"),
                    ("solution", "Customer records help", "ServiZephyr customer history aur workflow ko organize karta hai.", "restaurant manager customer tablet", "relief"),
                    ("benefit", "Better service memory", "Complaint, preference aur repeat visits visible.", "happy customer restaurant owner", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Delivery Area Confusion",
                "hook": "Order aa gaya, area bahar.",
                "pain_point": "Delivery range and charges clear na ho to staff-customer friction hota hai.",
                "idea_summary": "Delivery area confusion becomes rule-based control.",
                "caption": "Delivery rule clear nahi hua to order lene ke baad awkward scene hota hai.",
                "slides": [
                    ("hook", "Area Bahar Nikla", "Order accept hua. Address delivery range ke bahar.", "restaurant delivery bag counter", "confusion"),
                    ("setup", "Staff customer ko call kare", "Sir, yahan delivery possible nahi hai.", "restaurant staff phone delivery", "stress"),
                    ("conflict", "Customer angry", "Order lete time kyun nahi bataya?", "angry customer phone restaurant", "frustration"),
                    ("emotion", "Brand image hit", "Small rule miss, big trust issue.", "restaurant owner worried phone", "stress"),
                    ("solution", "Rules in system", "ServiZephyr delivery range, charges aur blocked areas organize karta hai.", "delivery map tablet restaurant", "relief"),
                    ("benefit", "Less manual confusion", "Area, charge aur delivery flow clearer.", "restaurant delivery staff organized", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "GST Bill Pressure",
                "hook": "Customer ne GST bill maanga.",
                "pain_point": "Custom taxes and charges manual hone par billing pressure badhta hai.",
                "idea_summary": "Tax/bill pressure becomes configurable billing control.",
                "caption": "Professional billing restaurant ki credibility banati hai.",
                "slides": [
                    ("hook", "GST Bill Pressure", "Customer: GST bill mil jayega?", "restaurant customer asking bill", "stress"),
                    ("setup", "Counter check kare", "Tax, charge, discount - sab manually verify.", "cashier checking restaurant bill", "confusion"),
                    ("conflict", "Line wait kar rahi", "Ek custom bill, poora counter slow.", "restaurant billing queue", "frustration"),
                    ("emotion", "Owner wants clean billing", "Professional experience billing se bhi dikhta hai.", "restaurant owner billing counter", "stress"),
                    ("solution", "Smart billing flow", "ServiZephyr custom taxes, charges aur billing settings support karta hai.", "restaurant pos billing screen", "relief"),
                    ("benefit", "Bills feel professional", "Customer ko clarity, owner ko control.", "receipt pos restaurant counter", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Multi-Branch Mess",
                "hook": "Do branches. Do alag stories.",
                "pain_point": "Multi-branch operations without central visibility owner ko blind spots dete hain.",
                "idea_summary": "Multi-branch mess becomes centralized operational clarity.",
                "caption": "Branch badhna achha hai, par control bhi saath badhna chahiye.",
                "slides": [
                    ("hook", "Multi-Branch Mess", "Branch A busy. Branch B slow. Owner confused.", "restaurant owner multiple cafe branches", "confusion"),
                    ("setup", "Reports alag-alag", "Ek branch WhatsApp, ek branch notebook, ek branch calls.", "restaurant manager paperwork laptop", "confusion"),
                    ("conflict", "Decision late hota hai", "Kahan staff chahiye? Kahan offer? Kahan issue?", "business owner stressed charts", "frustration"),
                    ("emotion", "Growth feels heavy", "Branch badhi, par control scatter ho gaya.", "restaurant owner stressed laptop", "stress"),
                    ("solution", "Central visibility", "ServiZephyr multi-branch management ko organize karne me help karta hai.", "restaurant analytics dashboard tablet", "relief"),
                    ("benefit", "Growth with control", "Orders, billing, customers aur operations clearer across branches.", "restaurant owner confident tablet", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "WhatsApp Order Flood",
                "hook": "Chat me order, kitchen me doubt.",
                "pain_point": "WhatsApp orders manually forward karne se details miss ho sakti hain.",
                "idea_summary": "Chat order flood becomes structured ordering workflow.",
                "caption": "WhatsApp par order lena easy hai, manage karna tough ho sakta hai.",
                "slides": [
                    ("hook", "WhatsApp Order Flood", "Customer chat me order bhej raha. Staff busy hai.", "restaurant staff phone whatsapp order", "stress"),
                    ("setup", "Details miss ho gayi", "Address, item, quantity - kuch na kuch reh gaya.", "waiter checking phone restaurant", "confusion"),
                    ("conflict", "Kitchen wrong prep", "Order forward hua, par clear format me nahi.", "restaurant kitchen confused order", "frustration"),
                    ("emotion", "Owner ko structure chahiye", "Chat orders ko bhi proper workflow chahiye.", "restaurant owner phone stressed", "stress"),
                    ("solution", "Ordering flow structured", "ServiZephyr online and WhatsApp ordering ko organize karta hai.", "restaurant online order tablet", "relief"),
                    ("benefit", "Less chat chaos", "Order details, status aur billing connected.", "restaurant staff tablet order", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Owner Firefighting",
                "hook": "Owner sab kuch khud kar raha.",
                "pain_point": "Owner dependency high ho to system scalable nahi hota.",
                "idea_summary": "Owner firefighting becomes process-driven control.",
                "caption": "Restaurant owner ka kaam har chhoti problem me phasna nahi, business grow karna hai.",
                "slides": [
                    ("hook", "Owner Firefighting", "Order issue? Owner. Bill issue? Owner. Customer issue? Owner.", "restaurant owner multitasking stressed", "stress"),
                    ("setup", "Team wait karti hai", "Decision ke liye har baar owner ko call.", "restaurant staff calling owner", "confusion"),
                    ("conflict", "Business owner stuck", "Growth planning ka time daily chaos kha jata hai.", "business owner tired restaurant", "frustration"),
                    ("emotion", "Control missing hai", "Owner busy hai, par system mature nahi.", "restaurant owner holding head", "stress"),
                    ("solution", "Process takes load", "ServiZephyr workflows ko structured aur visible banata hai.", "restaurant workflow tablet", "relief"),
                    ("benefit", "Owner gets control back", "Team ka kaam clear. Owner ka view clear.", "restaurant owner confident cafe", "control"),
                    cta_slide,
                ],
            },
            {
                "title": "Daily Report Missing",
                "hook": "Din khatam. Report kahan?",
                "pain_point": "Daily sales, items, customers aur staff insights missing ho to decisions guesswork ban jaate hain.",
                "idea_summary": "Missing reports become analytics-backed decisions.",
                "caption": "Restaurant ka daily report owner ke liye business health check hota hai.",
                "slides": [
                    ("hook", "Daily Report Missing", "Raat ko owner poochta: aaj kya sell hua?", "restaurant owner checking reports night", "confusion"),
                    ("setup", "Staff guesses", "Paneer zyada gaya hoga. Maybe biryani bhi.", "restaurant staff discussing sales", "confusion"),
                    ("conflict", "Decision guesswork", "Kal stock kya rakhna hai? Offer kis item par?", "restaurant owner inventory calculator", "frustration"),
                    ("emotion", "Data chahiye", "Feeling se business nahi, clarity se grow hota hai.", "restaurant owner laptop stressed", "stress"),
                    ("solution", "Analytics help", "ServiZephyr item, customer aur business insights organize karta hai.", "restaurant analytics dashboard", "relief"),
                    ("benefit", "Tomorrow gets smarter", "Top items, customers aur patterns visible.", "restaurant owner smiling analytics tablet", "control"),
                    cta_slide,
                ],
            },
        ]

    def _restaurant_meme_fallback(self, cta: str) -> dict[str, Any]:
        return {
            "topic": {
                "reel_topic": "Restaurant order chaos vs smart control",
                "hook": "Customer: mera order kahan hai? Staff: kis order ki baat ho rahi hai?",
                "audience_pain_point": "Restaurant teams lose time when dine-in, pickup, delivery, billing, and waiting updates are scattered.",
                "cta": cta,
                "idea_summary": "A funny restaurant chaos scene where ServiZephyr Restaurant brings orders, billing, waiting, and staff workflow into control.",
            },
            "script": {
                "short_reel_script": (
                    "Customer asks where the order is. Waiter checks one place, cashier checks another, kitchen says nothing arrived. "
                    "Owner enters stress mode. Then ServiZephyr Restaurant puts order status, billing, waiting, and staff workflow in one controlled system."
                ),
                "voiceover_script": (
                    "Restaurant me order, billing, waiting aur staff updates alag alag chal rahe hain? "
                    "Tab chaos free me milta hai. ServiZephyr Restaurant se owner ko business, customer aur control ek jagah milta hai."
                ),
                "subtitles": [
                    "Customer: order kahan hai?",
                    "Waiter: cashier se pucho.",
                    "Cashier: kitchen se pucho.",
                    "Kitchen: order aaya kab?",
                    "Owner: bas karo yaar.",
                    "ServiZephyr: control ek jagah.",
                    cta,
                ],
                "scenes": [
                    {
                        "scene_number": 1,
                        "visual": "Restaurant staff looking confused near counter",
                        "on_screen_text": "Customer: order kahan hai?",
                        "voiceover": "Customer asks where the order is.",
                    },
                    {
                        "scene_number": 2,
                        "visual": "Waiter, cashier, and kitchen team checking different places",
                        "on_screen_text": "Staff: kis screen pe dekhein?",
                        "voiceover": "Staff checks different places and confusion grows.",
                    },
                    {
                        "scene_number": 3,
                        "visual": "Restaurant owner stressed during busy rush",
                        "on_screen_text": "Owner: control chahiye, comedy nahi.",
                        "voiceover": "The owner needs control, not daily comedy.",
                    },
                    {
                        "scene_number": 4,
                        "visual": "Clean restaurant dashboard with orders and billing organized",
                        "on_screen_text": "ServiZephyr = control ek jagah",
                        "voiceover": "ServiZephyr Restaurant brings restaurant control into one place.",
                    },
                ],
            },
            "caption": {
                "instagram_caption": (
                    "Restaurant ka chaos funny tab tak hai jab tak customer wait nahi kar raha. "
                    "ServiZephyr Restaurant helps owners manage orders, billing, waiting, staff workflow, and customer records with more control."
                ),
                "hashtags": [
                    "#ServiZephyr",
                    "#RestaurantSoftware",
                    "#RestaurantOwner",
                    "#CafeBusiness",
                    "#FoodBusiness",
                    "#RestaurantManagement",
                    "#BillingSoftware",
                    "#DineIn",
                    "#RestaurantMarketing",
                    "#BusinessControl",
                ],
                "cta": cta,
                "engagement_prompt": "Restaurant me sabse zyada chaos kis cheez se hota hai?",
            },
                "meme": {
                    "top_text": "Customer: order kahan hai?",
                    "bottom_text": "ServiZephyr: control ek jagah",
                    "template_hint": "drake hotline bling",
                    "frames": [
                        {
                            "top_text": "Rush hour starts",
                            "bottom_text": "Owner: aaj smooth chalega",
                            "template_hint": "drake",
                        },
                        {
                            "top_text": "Customer: order kahan hai?",
                            "bottom_text": "Staff: kis screen pe dekhein?",
                            "template_hint": "two buttons",
                        },
                        {
                            "top_text": "Owner after 5 minutes",
                            "bottom_text": "Control chahiye, daily drama nahi",
                            "template_hint": "expanding brain",
                        },
                        {
                            "top_text": "ServiZephyr",
                            "bottom_text": "Orders, billing, waiting - ek jagah",
                            "template_hint": "change my mind",
                        },
                    ],
                },
            "video_prompts": {
                "style": "Funny restaurant meme reel, fast cuts, expressive captions, busy counter, kitchen rush, clean solution reveal.",
                "prompts": [
                    "Restaurant customer waiting at counter while staff look confused, vertical meme reel.",
                    "Waiter cashier and kitchen team checking different places during busy restaurant rush.",
                    "Restaurant owner stressed at billing counter during peak hours, funny relatable expression.",
                    "Clean restaurant management dashboard organizing orders billing waiting and staff workflow.",
                ],
            },
        }

    def _sanitize(self, value: Any) -> Any:
        blocked_names = [
            "zomato",
            "swiggy",
            "ubereats",
            "uber eats",
            "magicpin",
            "dotpe",
            "petpooja",
            "posist",
            "urbanpiper",
            "toast",
            "square",
            "clover",
        ]
        if isinstance(value, str):
            cleaned = value
            for name in blocked_names:
                cleaned = cleaned.replace(name, "restaurant app")
                cleaned = cleaned.replace(name.title(), "restaurant app")
                cleaned = cleaned.replace(name.upper(), "restaurant app")
            return cleaned
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        if isinstance(value, dict):
            return {key: self._sanitize(item) for key, item in value.items()}
        return value

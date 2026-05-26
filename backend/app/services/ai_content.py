import json
from typing import Any

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
        return {
            "topic": {
                "reel_topic": "Peak Hour ka Darr",
                "hook": "7:30 PM. Restaurant full. Aur system full confused.",
                "audience_pain_point": "Restaurant owners lose control when dine-in, pickup, billing, waiting, and staff updates are scattered.",
                "cta": cta,
                "idea_summary": "A story carousel about peak-hour chaos turning into control with ServiZephyr Restaurant.",
            },
            "script": {
                "short_reel_script": "A 7-slide carousel story showing peak-hour restaurant chaos and the shift to ServiZephyr Restaurant.",
                "voiceover_script": "",
                "subtitles": [
                    "7:30 PM. Peak hour start.",
                    "Table 4 ka order kitchen tak gaya hi nahi.",
                    "Customer: bhai mera order kahan hai?",
                    "Owner: dine-in, pickup, billing sab alag chal raha hai.",
                    "Then the restaurant shifted to ServiZephyr.",
                    "Orders. Billing. Tracking. Waiting. One system.",
                    "Business, Customer & Control. All Yours.",
                ],
                "scenes": [],
            },
            "caption": {
                "instagram_caption": (
                    "Peak hour ka chaos har restaurant owner samajhta hai. "
                    "ServiZephyr helps bring orders, billing, waiting, tracking, and staff workflow into one controlled system. "
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
                "top_text": "Peak hour",
                "bottom_text": "Owner stress level: 100",
                "template_hint": "drake",
            },
            "carousel": {
                "title": "Peak Hour ka Darr",
                "slides": [
                    {
                        "slide_number": 1,
                        "role": "hook",
                        "headline": "Peak Hour ka Darr",
                        "body": "7:30 PM. Restaurant full. Owner already alert mode me.",
                        "visual_direction": "crowded restaurant evening rush",
                        "emotion": "anticipation",
                    },
                    {
                        "slide_number": 2,
                        "role": "setup",
                        "headline": "Table 4 ka order?",
                        "body": "Waiter: kitchen tak gaya hoga. Kitchen: kaunsa order?",
                        "visual_direction": "waiter confused near kitchen counter",
                        "emotion": "confusion",
                    },
                    {
                        "slide_number": 3,
                        "role": "conflict",
                        "headline": "Customer ka patience gaya",
                        "body": "Bhai mera order 40 min se kahan hai?",
                        "visual_direction": "customer waiting at table",
                        "emotion": "frustration",
                    },
                    {
                        "slide_number": 4,
                        "role": "emotion",
                        "headline": "Owner ka real stress",
                        "body": "Dine-in alag. Pickup alag. Billing alag. Waiting list alag.",
                        "visual_direction": "restaurant owner stressed at billing counter",
                        "emotion": "stress",
                    },
                    {
                        "slide_number": 5,
                        "role": "solution",
                        "headline": "Then they shifted",
                        "body": "ServiZephyr brought the workflow into one place.",
                        "visual_direction": "clean modern restaurant dashboard",
                        "emotion": "relief",
                    },
                    {
                        "slide_number": 6,
                        "role": "benefit",
                        "headline": "Orders. Billing. Waiting.",
                        "body": "Tracking, staff roles, customers and control - all connected.",
                        "visual_direction": "organized restaurant operation",
                        "emotion": "control",
                    },
                    {
                        "slide_number": 7,
                        "role": "cta",
                        "headline": "DM 'RESTAURANT' Now!",
                        "body": "Visit https://www.servizephyr.com or message us to bring control into one place.",
                        "visual_direction": "minimal brand end card no photo",
                        "emotion": "confidence",
                    },
                ],
            },
            "video_prompts": {
                "style": "Premium restaurant story carousel, modern brand design, emotional but clean.",
                "prompts": [
                    "Crowded restaurant during dinner rush.",
                    "Confused waiter near kitchen counter.",
                    "Customer waiting for food at table.",
                    "Restaurant owner stressed near billing counter.",
                    "Clean restaurant management dashboard.",
                    "Organized staff workflow in restaurant.",
                    "Minimal ServiZephyr brand card.",
                ],
            },
        }

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

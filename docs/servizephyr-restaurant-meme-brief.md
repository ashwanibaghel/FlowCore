# ServiZephyr Restaurant Meme Content Brief

## Product

ServiZephyr Restaurant is a restaurant technology platform for restaurants, cafes, dhabas, QSRs, cloud kitchens, and local food businesses.

Tagline: Business, Customer & Control — All Yours.

## What It Helps With

- Online ordering through a WhatsApp-based flow
- Pickup and delivery orders
- Live order status tracking
- Dine-in QR ordering
- Seat occupancy and table workflow
- Waiting queue, token generation, and seating management
- Billing, thermal printer support, custom taxes, charges, and GST settings
- Coupons and offers
- Customer records, order history, repeat customers, top customers, and item insights
- Delivery range, delivery charges, blocked areas, and custom delivery rules
- Staff roles for waiter, chef, cashier, manager, and owner
- Multi-branch management
- Borrower or khata-style pending payment tracking

## Script Rules

- Show restaurant pain first, then show ServiZephyr Restaurant as the solution.
- Do not mention, compare with, or hint at any third-party brand, app, delivery marketplace, POS, or competitor by name.
- Keep the content focused on restaurant chaos, owner stress, staff confusion, customer waiting, billing problems, dine-in confusion, waiting queues, delivery control, inventory-like operational confusion, and customer management.
- Use funny, relatable Hinglish by default.
- The tone should be meme-like, punchy, slightly dramatic, and never insulting.
- The structure should be: chaos setup -> funny punchline -> ServiZephyr Restaurant solution -> CTA.
- Do not overpromise revenue or guaranteed growth.
- Keep subtitles short for vertical reels.

## Good Meme Angles

- Customer asks where the order is and everyone checks a different place.
- Cashier panic during rush hour billing.
- Owner trying to remember pending payments manually.
- Waiter confused about table status.
- Kitchen says the order never arrived.
- Customer waiting queue turns into crowd confusion.
- Owner opens sales records at night and regrets using notebooks.
- Staff asks owner everything because roles are not clear.
- Delivery areas and charges become manual headache.
- Coupon offer is running but staff forgot the rules.

## Default CTA

DM us the word RESTAURANT.

## Imgflip Meme Template Workflow

Imgflip can provide popular meme templates and can generate a captioned meme image through its API.

Setup:

1. Create a normal account at `https://imgflip.com/signup`.
2. Use the account username and password in `.env`.
3. Keep the password unique to Imgflip. Do not reuse an important personal password.

Required `.env` values:

```env
MEME_TEMPLATE_PROVIDER=imgflip
ENABLE_IMGFLIP_MEMES=true
IMGFLIP_USERNAME=
IMGFLIP_PASSWORD=
```

Notes:

- `https://api.imgflip.com/get_memes` can list popular templates without auth.
- `https://api.imgflip.com/caption_image` needs Imgflip username and password.
- The automation generates top and bottom meme text, creates a captioned meme image, then turns it into a vertical video with CTA, audio, and upload flow.
- Scripts must still avoid naming third-party restaurant, delivery, POS, or competitor apps.

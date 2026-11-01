# LibraAI v73 — Homepage, Audio Library & Shop Refresh

## এই রিলিজে যা পরিবর্তন হয়েছে
- Homepage-এ reference অনুযায়ী Listen & Discover editorial section এবং premium audiobook ranking layout যোগ হয়েছে।
- `/audio-library` পেজে ১৫টি audiobook ও ৫টি podcast sample catalogue, search/filter, browser-based preview এবং signed-in user bookmark persistence যুক্ত হয়েছে।
- `/shop` থেকে existing `/marketplace` storefront-এ যাওয়া যায়; development catalog-এ ৪০টি demo book/reader product, ratings, stock, discounts, category filters এবং trending/bestseller/popular sorting যুক্ত হয়েছে।
- Cart-এ quantity update, Buy Now থেকে checkout, এবং pre-login Add to Cart/AI Assistant access notice যোগ হয়েছে।
- Checkout-এ Online, Cash on Delivery, Bank Transfer এবং Standard/Pre-order preference নির্বাচন ও order record-এ সংরক্ষণ করা হয়।
- About আলাদা homepage page না রেখে homepage section করা হয়েছে; footer light glass/gradient treatment এবং Lora typography ব্যবহার করা হয়েছে।

## গুরুত্বপূর্ণ integration সীমা
- Existing backend order workflow sandbox/pending order তৈরি করে। bKash/Nagad/card-এর live charge নেওয়া হয় না; production gateway credentials, provider verification ও launch checks ছাড়া online payment চালু নয়।
- Audio catalogue-এর title/description হলো demo metadata; full audiobook/podcast playback-এর জন্য licensed audio assets ও hosting configure করতে হবে। Preview browser speech synthesis দিয়ে sample description পড়ে।
- Demo catalogue seed কেবল non-production environment-এ চলে; production inventory বা rights data overwrite করে না।

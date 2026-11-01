# LibraAI v52 — PDF Page Position Controls

## কী যোগ হয়েছে
- Licensed PDF খোলার সময় একই বই/ফাইলের সংরক্ষিত page position থাকলে সেটি browser PDF viewer-এর `#page=N` fragment দিয়ে restore করার চেষ্টা করে।
- PDF reader-এর উপরে page number input এবং “Go to page & sync” control যোগ হয়েছে। ব্যবহারকারী page number দিলে viewer ওই পৃষ্ঠায় যায় এবং account-scoped progress API-তে page/file/location সংরক্ষণ করে।
- পূর্ববর্তী EPUB/CBZ page-index ও audiobook timestamp sync, upload security এবং existing UI অপরিবর্তিত রাখা হয়েছে।
- নতুন contract tests PDF control, restore, manual sync এবং file binding যাচাই করে।

## সীমাবদ্ধতা
Browser-native PDF viewer-এর নিজস্ব toolbar দিয়ে page বদলালে cross-browser-এ সেই page number পড়ার কোনো নির্ভরযোগ্য standard API নেই। তাই v52-এর page tracking explicit/manual: উপরের control দিয়ে page নির্বাচন করে sync করতে হবে। এটি PDF.js-ভিত্তিক automatic scroll/page tracking নয়। EPUB position-ও এখনো পূর্ণ CFI/spine implementation নয়।

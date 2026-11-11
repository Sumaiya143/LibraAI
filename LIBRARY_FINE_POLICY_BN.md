# ১৪ দিনের Book Borrowing ও Fine Policy

- প্রতিটি বই ধার নেওয়ার পর ১৪ দিনের মধ্যে ফেরত দিতে হবে।
- Due date-এর পরের দিন থেকে প্রতিদিন BDT ১০ fine (default; `LIBRAAI_FINE_PER_DAY_PAISE=1000` দিয়ে পরিবর্তনযোগ্য) গণনা হবে।
- Fine integer paisa-তে সংরক্ষণ করা হয়, তাই floating-point rounding সমস্যা হয় না।
- Customer `/account/fines`-এ বইভিত্তিক overdue day, fine balance ও payment submission status দেখতে পারে।
- Overdue বই আগে ফেরত দিতে হবে; তারপর approved payment channel-এ টাকা পরিশোধ করে transaction reference জমা দিতে হবে।
- Payment reference জমা দিলেই fine পরিশোধিত হয় না। Admin বাস্তব payment যাচাই করে `/admin/fines` থেকে approve করলে balance cleared হয়।
- Unpaid fine থাকলে নতুন বই borrow করা যাবে না। Payment pending থাকলেও balance unpaid থাকে।
- Fine সম্পূর্ণ পরিশোধ হলে `/account/library-clearance`-এ Library No-Dues Clearance দেখায়।
- এটি **Library No-Dues Clearance**, কোনো academic graduation certificate নয়। Academic certificate প্রদান/আটকে রাখার সিদ্ধান্ত সংশ্লিষ্ট শিক্ষা প্রতিষ্ঠানের নীতি ও প্রযোজ্য আইনের অধীন।
- Policy date `Asia/Dhaka` timezone ধরে; `LIBRAAI_LIBRARY_TIMEZONE` দিয়ে পরিবর্তন করা যায়।

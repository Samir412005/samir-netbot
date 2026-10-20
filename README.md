# Samir Netbot — الهاتف المستقل ومسار المزودات

## APK جاهز بلا استضافة
نسخة Android المستقلة في [mobile-only](https://github.com/Samir412005/samir-netbot/tree/mobile-only). [تحميل preview-3](https://github.com/Samir412005/samir-netbot/releases/tag/preview-3). الهاتف نفسه يسحب Telegram؛ لا Cloud VM ولا خادم مطلوب. أدخل توكن BotFather داخل التطبيق، ابدأ الخدمة واسمح بالإشعارات، ثم /start من حساب المالك. USSD الحقيقي يتطلب موافقة محلية واختيار SIM ولا يضمن قبول العرض من المشغّل.

## هذا الفرع: providers
[دليل الإعداد والعقد](providers/README.md) و[واجهة المستخدم المعطلة](providers/manual_otp.py). شغّل `python -m bot.provider_main` على جهازك مع Python 3.12 وBOT_TOKEN وPROVIDER=mock افتراضياً. mock/reloadly لا يحتاجان متطلبات البوت القديم؛ companion يحتاج متطلبات وجسر النسخة القديمة.
البوت يتضمن كتالوجاً، تأكيداً منفصلاً، نقاطاً/هدية، إدارة عروض للمالك، سجل تفعيل مقنّع ومنع تكرار SQLite. /admin يعرض الأوامر. manual_otp واجهة فقط ورسالتها «هذا المسار غير مفعّل»؛ لا تنفيذ OTP أو جلسات أو واجهات غير موثقة.

Reloadly اختياري عبر OAuth رسمي؛ افتراضه sandbox. التشغيل المدفوع يحتاج RELOADLY_SANDBOX=false وRELOADLY_LIVE_ENABLED=true، مفاتيح حساب ومحفظة ممولة ورقم مستفيد محلي وSKU ومشغّل مدعومين. تغطية الجزائر لم تتحقق بحساب حقيقي. النقاط لا تمول الشحن.

## حدود التشغيل
لم ننشر خادماً؛ كود Python يحتاج جهازاً يبقى شغالاً، والمفاتيح وحدها لا تشغل البوت 24/24. لا تشغّل Python وAPK بالتوكن نفسه في آن واحد. companion هنا جسر البنية القديمة وليس قناة تحكم في APK المستقل. الكود القديم محفوظ في هذا الفرع وmain للتوافق؛ نقطة تشغيل المزودات هي bot.provider_main لا bot.main.

## التحقق
[بناء APK واختباراته](https://github.com/Samir412005/samir-netbot/actions/runs/39445417458): 7 اختبارات، lint، بناء وتحقق توقيع debug. اختبارات Python في [Actions](https://github.com/Samir412005/samir-netbot/actions/workflows/providers.yml) تشمل mocks للـHTTP وtimeout والتزامن ومنع التكرار والواجهة المعطلة والنقاط والإدارة. لا اختبار SIM فعلي ولا live Telegram ولا شحن مدفوع.

لا ترفع .env أو أرقام أو قواعد البيانات أو مفاتيح API إلى Git. احفظ قواعد البيانات محلياً لمنع إعادة المدفوعات بعد إعادة التشغيل.

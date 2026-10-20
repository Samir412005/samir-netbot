# Providers preview — اختياري، منفصل عن تطبيق mobile-only

هذا الفرع `providers` مبني على نسخة Python القديمة في main. الـAPK المستقل يبقى في فرع `mobile-only` وإصدار [preview-3](https://github.com/Samir412005/samir-netbot/releases/tag/preview-3)، بلا استضافة. **طبقة Python ما تدخلش داخل APK**. البوت الجديد `python -m bot.provider_main` يختار المزوّد ويطلب تأكيداً من داخل Telegram؛ ليس نفس عملية تشغيل APK.

## الحدود المهمة
- مفاتيح Reloadly وحدها لا تعني بوت شغال: يلزم جهاز Python متصل بالإنترنت لتشغيله. لا نشرنا سيرفر ولا اشترينا استضافة ولا موّلنا محفظة ولا جربنا شحناً مدفوعاً.
- Reloadly يحتاج رقم المستفيد ويتقاضى رسوماً/رصيداً. هذا ليس USSD، وليس إنترنت مجاني ولا ضمان تفعيل باقة مشغل محددة. إذا ما تحبش إعطاء رقم لمزوّد خارجي، استعمل التطبيق المستقل ومسار USSD المحلي. لا نطلب رقماً ولا OTP في المحادثة؛ رقم Reloadly يضبط محلياً في RECIPIENTS_JSON فقط.
- لم يتم إثبات تغطية الجزائر أو مشغل معين دون حساب وصلاحيات وكتالوج حالي. كل operator_id تجريبي هنا غير صالح للشحن الحقيقي؛ لا تخمن المعرف.
- mock وReloadly sandbox يكتبا بوضوح محاكاة، حتى لو status=success. نجاح mock ليس تفعيل شريحة.

## التشغيل في جهازك
Python 3.12، والتجربة mock لا تحتاج أي مكتبة خارجية:
```
export BOT_TOKEN='ضعه محلياً ولا ترفعه'
export PROVIDER=mock
export MOCK_OUTCOME=success  # success|fail|timeout|pending
export IDEMPOTENCY_WINDOW=day  # hour|day
python -m bot.provider_main
```
البوت يسمح فقط للمالك 8178411819 في private chat. `/start` يعرض الكتالوج، الاختيار ثم تأكيد صالح لدقيقتين، `/history` يسرد المراجع والحالة والتكلفة، `/status sn-...` يفحص Reloadly بـGET دون إعادة شحن. لا تشغل أكثر من poller لنفس BOT_TOKEN (النسخة القديمة أو APK أو هذا المدخل). إعداد PROVIDER لا يغير bot.main القديم؛ استعمل **bot.provider_main** صراحةً.

انسخ `providers/catalog.example.json` إلى ملف خاص وعدّل PROVIDER_CATALOG بمساره. كل عرض له اسم وenabled وSku (id ثابت، operator_id من المزود، amount نص عشري موجب، currency عملة **مبلغ الطلب**، country=ISO مثل DZ، use_local_amount حسب الكتالوج، companion_bid للمرافق). الديمو operator_id=0 متعمد وغير صالح لـReloadly. إذا كان use_local_amount=false فالمبلغ بعملة محفظة الإرسال، وليس تلقائياً DZD؛ راجع كتالوج المزود. التطبيق لا يستنتج عروض الجزائر ولا الأسعار من الاسم.

## حساب Reloadly وOAuth
1. افتح حسابك في [Reloadly](https://www.reloadly.com/) وابدأ TEST/Sandbox. من Developers > API settings خذ client_id وclient_secret الخاصين بنفس البيئة. راجع متطلبات تفعيل الحساب من Reloadly قبل LIVE.
2. اقرأ [Quickstart الرسمي](https://developers.reloadly.com/airtime/quickstart) و[مرجع Airtime](https://docs.reloadly.com/airtime/Top-ups). الشحن الحقيقي يحتاج تمويل محفظة LIVE وكتالوج مشغّل متاح، وليس المفاتيح فقط. لا تدخل الأسرار في Git أو APK أو GitHub logs.
3. اضبط محلياً:
```
export PROVIDER=reloadly
export RELOADLY_CLIENT_ID='...'
export RELOADLY_CLIENT_SECRET='...'
export RELOADLY_SANDBOX=true
export RECIPIENTS_JSON='{"8178411819":"+213ضع_رقمك_محلياً"}'
export PROVIDER_CATALOG='/مسار/ملف-عروض-خاص.json'
python -m bot.provider_main
```
المثال ليس رقماً صالحاً. رقم المستفيد لازم E.164 صحيح؛ لا يكتب في السجل ولا يتكرر في رد البوت. دالة activate(msisdn, sku) تستعمله في HTTPS إلى Reloadly فقط.
4. OAuth POST إلى `https://auth.reloadly.com/oauth/token` بـgrant_type=client_credentials وaudience=`https://topups-sandbox.reloadly.com` أو `https://topups.reloadly.com`. الـbearer يبقى في ذاكرة العملية ويتجدد حسب expires_in. لا نعيد محاولة POST للشحن تلقائياً، حتى عند 401.
5. افحص تغطية الجزائر الحقيقية من Pricing > Airtime في حسابك، وبـ`ReloadlyProvider.operators('DZ')` (GET `/operators/countries/DZ`) في البيئة الملائمة. راجع المشغل وdata/bundle ودلالات fixedAmounts/min/max والعملة/الرسوم. Sandbox ليس دليلاً على توفر LIVE. لا تضع عرضاً enabled قبل التأكد من الكتالوج والتكلفة.
6. بعد تحقق يدوي في sandbox، LIVE يحتاج **معاً** `RELOADLY_SANDBOX=false` و`RELOADLY_LIVE_ENABLED=true` ومفاتيح LIVE ومحفظة ممولة وعرضاً صحيحاً ورقم مستفيد موافقاً. البوت يعرض مبلغ الطلب ويطلب تأكيداً قبل الإرسال؛ التكلفة النهائية الفعلية تسجل من balanceInfo.cost وعملتها من الرد، وقد تختلف عن amount بسبب الرسوم/الخصومات/FX. لا تعدّ amount سقفاً مضموناً للتكلفة. لم ننفّذ أي عملية LIVE هنا.

## الحالات والسجل ومنع التكرار
`ActivationResult(ref,status,message,raw_sanitized,cost,currency)`، status واحدة من success/failed/pending/unknown. SUCCESSFUL=success، PROCESSING/PENDING=pending، FAILED/REFUNDED=failed، غير المعروف=unknown. OAuth/validation قبل إرسال الشحن يفشل بأمان؛ socket timeout أو 5xx بعد إرسال topup يرجع unknown، لا success ولا retry.

SQLite يسجل المرجع المحلي sn-... ومرجع المزود داخل result، المستخدم والعرض والمزوّد والتوقيت والحالة والتكلفة المؤكدة (قد تكون null حتى تأكيد الرد). لا نخزن msisdn أو أسرار أو PIN/raw payload. raw_sanitized قائمة حقول مسموحة فقط. معاملات BEGIN IMMEDIATE وحجز دائم قبل الشبكة يمنعان التكرار المتزامن؛ نفس user+offer في نافذة ساعة/يوم يرجّع السجل السابق حتى لو فشل، مع حماية rolling window قرب حدود UTC. pending/unknown يمنعان إعادة نفس العرض **حتى بعد مرور أيام** إلى أن تتضح النتيجة. انهيار العملية بعد الحجز يترك pending ولا يعيد الشحن؛ فضّل الحماية على خصم مكرر.

customIdentifier يحمل المرجع المحلي لكنه **ليس وعداً من Reloadly بضمان idempotency**. الضمان المحلي يعتمد على الاحتفاظ بنفس SQLite وعدم حذفه/تشغيل نسخ بقواعد مختلفة. لا يوجد failover بعد إرسال غير مؤكد، حتى في auto. `auto` يختار Reloadly إذا وجدت المفاتيح، وإلا companion إذا COMPANION_ENABLED=true، وإلا mock معلن. فشل الإعداد لا يحول عملية live لمحاكاة نجاح.

لـpending بمعرّف transactionId، `/status sn-...` يقرأ [GET /topups/{transactionId}/status](https://www.reloadly.com/blog/how-does-the-get-top-up-status-endpoint-work/) ويحدث السجل دون شحن جديد. timeout دون transactionId يلزم مراجعة لوحة المزود بـcustomIdentifier يدوياً؛ لا تفتح الحظر بحذف SQLite. لا نضمن انتهاء pending تلقائياً، ولا نعيد الطلب بعد 30 دقيقة آلياً.

## companion كبديل صريح
providers/companion.py يوصل إلى **الجسر القديم** core.service.create_command: يلزم تشغيل الـAPI القديم، تطبيق المرافق القديم مربوطاً، وصلاحية اتصال/شريحة وموافقة محلية. المرجع وpending لا يعنيان نجاحاً؛ `/history` في البوت القديم يتابع نتيجة الجهاز. **لا يمكن ربط Python adapter مباشرة بتطبيق mobile-only** لأنه صار هو البوت وليس جهاز polling للجسر. التطبيق المستقل بديل تشغيل كامل وليس endpoint. لم نفتح سيرفراً لطبقة companion ولا تجاوزنا الموافقة. في بيئة legacy ثبت requirements.txt وجهز DB وفق README الأصلي.

## الاختبارات
```
python -m unittest tests.test_providers -v
```
Mock HTTP لا يستعمل مفاتيح فعلية ولا يرسل شحناً. الاختبارات تتحقق من OAuth audience وطلب topups وrecipientPhone/customIdentifier، التنقيح، حالات النجاح/الفشل/timeout و5xx، منع LIVE افتراضياً، منع التكرار مع restart/concurrency/window وunknown، companion بدون جهاز لا يدعي النجاح، GET للمراجعة وwhitelist. [GitHub Actions](https://github.com/Samir412005/samir-netbot/actions/workflows/providers.yml) يشغلها ويحفظ provider-tests.txt. اختبارات Android وتقاريرها تبقى في فرع mobile-only وإصدار preview-3.


## manual_otp ومسؤولية المستخدم
`PROVIDER=manual_otp` مدعوم صراحةً لكن غير مفعّل؛ الافتراضي mock وauto لا يختاره. يظهر في البوت «هذا المسار غير مفعّل». الملف manual_otp.py واجهة فقط ترمي NotImplementedError؛ لا نجمع OTP ولا ننفذ جلسات أو واجهات مشغّل غير موثقة.
العقد: activate(msisdn,sku) يعيد ActivationResult(ref,status,message,raw_sanitized,cost,currency). الحالات success/failed/pending/unknown؛ حجز SQLite قبل الإرسال، ومنع تكرار المستخدم+العرض ساعة/يوم، وتعليق unknown/pending دون إعادة تلقائية. السجلات قائمة سماح مقنعة بلا رقم/OTP/token/جلسة. [العقد التفصيلي وطريقة ربط وحدة المستخدم](MANUAL_CONTRACT.md).

## البوت والإدارة
المالك المسموح وحده: حساب Telegram المهيأ في الكود؛ خاص فقط. /start كتالوج ثم تأكيد مستقل لمدة دقيقتين؛ /points و/gift (10 كل 24 ساعة)؛ /admin و/offer KEY JSON و/enable KEY on|off لإدارة عروض الكتالوج المحلي؛ /history للتفعيل و/logs لآخر 50 حدثاً؛ /5g و/snap قريباً. العرض الجديد موقوف حتى تفعيله. تغيير الكتالوج يلغي التأكيدات المعلّقة. لا تحفظ أسراراً في أسماء العروض أو JSON.
نقاط البوت محلية تجريبية؛ لا تخصم/تمول محفظة Reloadly ولا تمنح إنترنت مجانياً. قاعدة الحالة BOT_STATE_DB مستقلة عن PROVIDER_DB؛ احتفظ بالاثنتين. PROVIDER_CATALOG الافتراضي provider-catalog.local.json (ينسخ المثال أول تشغيل).
اختبارات إضافية: python -m unittest discover -s tests -p 'test_provider*.py' -v ثم test_manual_otp.py.

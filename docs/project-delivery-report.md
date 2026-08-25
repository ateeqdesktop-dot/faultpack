# FaultPack v0.2 — Project Delivery Report

## Executive summary

تم اختيار وتطوير **FaultPack** بوصفه المشروع الرئيسي الذي يضيف تنوعًا هندسيًا حقيقيًا إلى حساب GitHub. يحوّل FaultPack فشلًا برمجيًا إلى حزمة إعادة إنتاج محمولة، منقحة للخصوصية، قابلة للتحقق وإعادة التشغيل والتقليل، ومناسبة للاستهلاك داخل CI. استُخدم المستودع الموجود `ateeqdesktop-dot/faultpack` كنقطة انطلاق بدل إنشاء مشروع آخر متشابه.

القرار يعالج مشكلة عملية: سجلات الفشل ولقطات الشاشة لا تمنح maintainer عقدًا قابلًا للتحقق يحدد revision والأمر والمدخلات والبيئة والسلوك المتوقع. FaultPack يقدّم هذا العقد كملفات عادية، من دون حساب مستضاف أو API key أو model call أو رفع ضمني.

## Account diagnosis

تضم قائمة الحساب المرصودة نحو 50 مستودعًا، منها 40 Python و8 TypeScript ومستودع Dart واحد. يتركز الحساب بقوة في AI-agent governance وMCP وprovenance وevidence وreplay وquality gates. توجد قدرة واضحة على بناء MVPs منظمة تحتوي على README وLICENSE وSECURITY وCONTRIBUTING واختبارات وGitHub Actions، لكن عددًا من المستودعات لا يتجاوز 1–3 التزامات، وكل المستودعات المرصودة بلا نجوم عامة وقت التدقيق. كما أن مستودع الملف الشخصي لا يحتوي README فعالًا.

لهذا السبب تجنب المشروع الجديد تكرار MCP gateway أو trace ledger أو policy control plane أو agent replay harness. FaultPack يعيد استخدام نقاط القوة في integrity وredaction وdeterminism، لكنه ينقلها إلى أدوات مطورين عامة تخدم أعطال المشاريع حتى عندما لا يكون الذكاء الاصطناعي جزءًا من النظام.

## Research and competitive decision

أظهر البحث أن ReproZip ناضج في التقاط system calls والاعتماديات لبناء حزم تجارب قابلة لإعادة التشغيل عبر chroot أو Vagrant أو Docker، مع تاريخ GitHub كبير ومجتمع قائم [1] [2]. rr قوي في record/replay منخفض المستوى وreverse debugging، لكنه يعتمد على متطلبات kernel وعتاد/VM محددة ولا يقدم عقد مشاركة عام لتذكرة فشل [3] [4]. BugZoo يوفر حاويات وواجهات CLI/Python/REST لدراسة أعطال تاريخية، بينما BugsInPy موجه إلى benchmark بحثي منظم لأعطال Python [5] [6]. LIBRO يثبت قيمة توليد اختبارات إعادة الإنتاج باستخدام LLM، لكنه replication package بحثي يتطلب Docker وبيئات وموارد أكبر [7].

الفجوة القابلة للدفاع ليست منافسة هذه الأدوات في التقاط نظام التشغيل أو debugging منخفض المستوى. الفجوة هي طبقة maintainer صغيرة: failure contract، input selection، privacy redaction، artifact integrity، verifier بلا تنفيذ، replay من workspace مختلف، reducer bounded، وتقارير CI ثابتة. يمكن لهذه الطبقة أن تتكامل مستقبلًا مع أدوات أعمق بدل استبدالها.

## Scoring decision

قُيّمت خمس أفكار عبر 18 معيارًا من 10، بإجمالي أقصى 180. الدرجات هي حكم هندسي استراتيجي مستند إلى تدقيق الحساب والبحث التنافسي وليست وعدًا بعدد النجوم.

| الفكرة | المجموع | المتوسط | الموقف |
| --- | ---: | ---: | --- |
| FaultPack — حزم إعادة إنتاج الأعطال | **168** | 9.33 | مختارة |
| MaintainerAtlas — مترجم قرارات الإصدار | 153 | 8.50 | احتياط |
| Miqyas — بوابات جودة OCR العربية | 150 | 8.33 | موجودة ومتخصصة |
| ProofMesh — أدلة تنفيذ AI موقعة | 149 | 8.28 | تكرار موضوعي |
| SignalBudget — بوابات cardinality/schema | 143 | 7.94 | احتياط نيش |

حصل FaultPack على أعلى قيمة لأنه يقدم developer value مباشرة، قابلية Open Source وCI مرتفعة، مساحة اختبار وتوثيق واسعة، ونقطة تنويع واضحة عن المحفظة الحالية.

## Delivered implementation

الإصدار `0.2.0` يضم manifest versioned يدعم `0.1` و`0.2`، ملفات input منتقاة وآمنة مع SHA-256، بيئة child دنيا مع `--env` allowlist، redaction قبل الكتابة والhashing، HMAC اختياري، بصمة v0.2 مستقرة تستبعد timestamp وpack ID ومدة التنفيذ المتغيرة، وZIP deterministic.

تضم واجهة CLI أوامر `capture` و`inspect` و`verify` و`replay` و`reduce` و`version`. يعمل `replay` داخل workspace مؤقت بمهلة محددة، ويقارن exit code وregex وoutput hashes وduration limits عند التصريح بها. يعمل `reduce` على UTF-8 text inputs بأسلوب bounded line-oriented delta debugging ويحافظ على failure oracle المطابق. تُنتج التقارير بصيغ Markdown وSARIF وJUnit، مع JSON مناسب للأتمتة.

يتضمن المستودع fixture end-to-end حقيقيًا تحت `fixtures/`: يمكن التحقق منه وإعادة تشغيله وتقليله دون شبكة. كما تم تحديث README وarchitecture وschema وSECURITY وCHANGELOG وGitHub Actions. يختبر workflow إصدارات Python 3.10–3.13، lint، mypy، pytest، build، وتدفق fixture الكامل.

## Security boundary

FaultPack ليس sandbox ولا يضمن network isolation أو إزالة كل PII. هذه الحدود موثقة في README وSECURITY. يمنع التنفيذ غير المقصود أثناء verify، يرفض traversal وabsolute paths وbackslash وsymlink escapes، يقلل البيئة الموروثة، ويضع حدًا زمنيًا للتشغيل وحدًا لعدد reducer runs. يجب تشغيل حزم خارجية في runner أو container معزول ومن دون credentials.

## Verification results

نجحت محليًا 14 اختبارات مع تغطية **91.68%**، ونجح `ruff check src tests`، و`mypy src`، وبناء `faultpack-0.2.0-py3-none-any.whl` و`faultpack-0.2.0.tar.gz`. كما نجح تدفق fixture الكامل: capture لحالة فشل، verify للبصمات، replay مع verdict مطابق، ثم reduce بأربع تشغيلات في المثال. لم يُدّعَ نجاح GitHub Actions قبل دفع التغييرات؛ workflow أصبحت جاهزة للتشغيل بعد النشر.

## Roadmap

بعد تثبيت عقد v0.2، تكون الإضافات المنطقية هي adapters لـpytest وJest وGo test، replay عبر OCI/Podman، Ed25519 وartifact attestations، differential replay matrices، browser/network adapters، وcorpus عامة مجهّلة. يجب أن تبقى هذه الطبقات additive وأن تستهلك pack/verdict contracts المستقرة بدل توسيع القلب بشكل غير منضبط.

## References

[1]: https://www.reprozip.org/about.html "About ReproZip"
[2]: https://github.com/VIDA-NYU/reprozip "ReproZip على GitHub"
[3]: https://rr-project.org/ "rr project overview"
[4]: https://github.com/rr-debugger/rr "rr على GitHub"
[5]: https://github.com/squaresLab/BugZoo "BugZoo على GitHub"
[6]: https://github.com/soarsmu/BugsInPy "BugsInPy على GitHub"
[7]: https://github.com/coinse/libro "LIBRO على GitHub"

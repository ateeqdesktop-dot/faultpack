# FaultPack — Project Delivery Report

## Executive summary

تم اختيار وبناء **FaultPack** بوصفه مشروعًا رئيسيًا يضيف تنوعًا هندسيًا حقيقيًا إلى حساب GitHub: أداة محلية وGitHub-native لتحويل فشل برمجي إلى حزمة إعادة إنتاج محمولة، منقحة الخصوصية، قابلة للتحقق وإعادة التشغيل. المستودع متاح الآن على [GitHub](https://github.com/ateeqdesktop-dot/faultpack)، والإصدار الأول منشور في [v0.1.0](https://github.com/ateeqdesktop-dot/faultpack/releases/tag/v0.1.0).

## Account diagnosis

يعرض الملف الشخصي هوية AI/ML وPython وNLP وComputer Vision، ويحتوي الحساب على 37 مستودعًا عامًا و0 متابعين وفق لقطة التدقيق. تحليل المستودعات الأصلية أظهر تركّزًا شديدًا في AI-agent governance وMCP وprovenance وevidence وquality gates. وفي المقابل، كان التمثيل الأضعف هو أدوات المطورين العامة، ومسارات صيانة Open Source ذات دورة استخدام واضحة، والمشاريع التي تخدم مطورين خارج نطاق AI.

القوة الواضحة هي القدرة على بناء MVPs ذات اختبارات وCI وتوثيق واهتمام بالسلامة. الخطر هو تكرار الفكرة تحت أسماء متعددة، مع أعمار صغيرة للمستودعات وغياب traction عام حتى الآن. لذلك صُمم FaultPack ليعيد استخدام نقاط القوة الحالية في integrity وredaction وdeterminism، لكن في مشكلة أوسع وأكثر قابلية للاكتشاف.

## Research and competitive decision

تبيّن المقارنة أن MCP Inspector مشروع ناضج للاختبار التفاعلي لـMCP، مع أكثر من 10 آلاف نجمة وبنية Web/CLI/TUI واسعة [1]. Phoenix منصة observability/evaluation كبيرة، مع tracing وdatasets وexperiments وprompt management [2]. Traccia يقدّم SDK قائمًا على OpenTelemetry للتتبع والتقييم والحوكمة [3]. أما Devtriage فيثبت قيمة التقاط الفشل وتوليد تقرير قابل للمشاركة، لكنه يظل CLI خفيفًا بعمق محدود [4]. ويقدم GitBug-Java benchmark بحثيًا لإعادات إنتاج أعطال Java، لا workflow عامًا للمشرفين [5].

كما تؤكد دراسة حديثة حول provenance أن الأنظمة المعقدة تحتاج إلى تتبع العملية لا النتيجة النهائية فقط، مع تحديات في schema موحد، وbenchmarks واقعية، والاستعادة، والخصوصية [6]. وتدعم GitHub رسميًا artifact attestations لإثبات مصدر وسلامة مخرجات البناء في المستودعات العامة [7]. الاستنتاج هو أن الفرصة ليست لوحة observability جديدة، بل حلقة maintainer كاملة: capture → sanitize → fingerprint → pack → replay → compare → publish.

| معيار القرار | FaultPack |
| --- | ---: |
| Originality | 9/10 |
| Technical depth | 9/10 |
| Real-world value | 10/10 |
| Developer and maintainer value | 10/10 |
| Open Source potential | 9/10 |
| Portfolio and recruiter value | 10/10 |
| Scalability and extensibility | 9/10 |
| Documentation/testing/CI potential | 10/10 |
| Total | **171/180** |

## Delivered implementation

يتضمن الإصدار الأول عقد manifest بإصدار `0.1`، canonical JSON وبصمة SHA-256، التقاط stdout/stderr، تنقيح الأسرار والرموز والبريد وعناوين IPv4، رفض traversal وsymlink، replay بمهلة محددة، مقارنة exit code وregex، وتقارير Markdown وSARIF وJUnit. كما يضم CLI أوامر `capture` و`inspect` و`verify` و`replay` و`version`، ومخطط JSON، وثيقة معمارية، README، سياسة أمان، CONTRIBUTING، Code of Conduct، قوالب Issues، وسير CI.

الحد الأمني موثق بوضوح: FaultPack ليس sandbox ولا يمنح replay أمانًا تلقائيًا ضد حزمة غير موثوقة. يجب استخدام runner أو container معزول عند التعامل مع حزم خارجية. هذه الصراحة جزء من تصميم المنتج وليست ملاحظة جانبية.

## Verification

أثبت التحقق المحلي نجاح 9 اختبارات مع تغطية 90.91%، ونجاح `ruff check .`، و`mypy src`، وبناء wheel `faultpack-0.1.0-py3-none-any.whl`. كما نجح smoke flow كامل: capture ثم verify ثم replay مع توليد التقارير الثلاثة. واختبار العبث غيّر fingerprint يدويًا وأثبت أن `verify` يرجع رمز الفشل المتوقع.

نجح GitHub Actions على Python 3.10 و3.11 و3.12 و3.13، مع jobs للجودة وsmoke، باستخدام `actions/checkout@v5` و`actions/setup-python@v6`. رابط آخر تشغيل ناجح هو [CI run](https://github.com/ateeqdesktop-dot/faultpack/actions/runs/32744913849).

## Roadmap

المرحلة التالية المنطقية هي adapters لـpytest وJest وGo test، ثم replay عبر Docker/Podman، وتعليقات GitHub App، والتحقق من artifact attestations، وdifferential replay matrices. أما browser/network capture وpublic anonymized corpus فهما امتدادان لاحقان بعد تثبيت العقد الأساسي وجمع feedback.

## References

[1]: https://github.com/modelcontextprotocol/inspector "MCP Inspector repository"
[2]: https://github.com/Arize-ai/phoenix "Arize Phoenix repository"
[3]: https://github.com/traccia-ai/traccia-py "Traccia repository"
[4]: https://github.com/DevMubarak1/Devtriage "Devtriage repository"
[5]: https://github.com/gitbugactions/gitbug-java "GitBug-Java repository"
[6]: https://arxiv.org/html/2606.04990v4 "From Agent Traces to Trust: A Survey of Evidence Tracing and Execution Provenance in LLM Agents"
[7]: https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations "GitHub artifact attestations documentation"

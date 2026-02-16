"""
Railbookers Chatbot -- Multilingual Translations
Supports: en, fr, es, de, it, hi, ja, zh, pt, ar
Use  t(key, lang)  for single strings.
Use  t_list(key, lang)  for suggestion lists.
Dynamic values use {placeholders} -- pass as kwargs to t().
"""

from typing import List


def t(key: str, lang: str = "en", **kwargs) -> str:
    """Return translated string, falling back to English."""
    entry = _T.get(key, {})
    text = entry.get(lang) or entry.get("en", key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def t_list(key: str, lang: str = "en") -> List[str]:
    """Return translated list (for suggestions), falling back to English."""
    entry = _TL.get(key, {})
    return list(entry.get(lang) or entry.get("en", []))


# ---------------------------------------------------------------------------
# Single-string translations
# ---------------------------------------------------------------------------
_T = {
    # ---- Welcome ----
    "welcome": {
        "en": (
            "Welcome to **Railbookers** -- the world's leading rail vacation specialist.\n\n"
            "I have access to **{pkg_count} curated rail journeys** spanning **50+ countries** -- from Alpine panoramas and luxury sleeper trains to iconic cultural routes.\n\n"
            "**Where would you like to go?**\n"
            "Name a country, city, or region -- or say **surprise me** and I will match you to the perfect journey."
        ),
        "fr": (
            "Bienvenue chez **Railbookers** -- le leader mondial des vacances en train.\n\n"
            "J'ai accès à **{pkg_count} voyages ferroviaires** dans **50+ pays** -- panoramas alpins, trains de nuit de luxe et routes culturelles emblématiques.\n\n"
            "**Où souhaitez-vous aller ?**\n"
            "Indiquez un pays, une ville ou une région -- ou dites **surprenez-moi**."
        ),
        "es": (
            "Bienvenido a **Railbookers** -- el especialista mundial en vacaciones en tren.\n\n"
            "Tengo acceso a **{pkg_count} viajes ferroviarios** en **50+ países** -- panoramas alpinos, trenes de lujo y rutas culturales icónicas.\n\n"
            "**¿Adónde le gustaría ir?**\n"
            "Indique un país, ciudad o región -- o diga **sorpréndame**."
        ),
        "de": (
            "Willkommen bei **Railbookers** -- dem weltweit führenden Bahnreise-Spezialisten.\n\n"
            "Ich habe Zugang zu **{pkg_count} Bahnreisen** in **50+ Ländern** -- Alpenpanoramen, Luxus-Schlafwagen und legendäre Kulturrouten.\n\n"
            "**Wohin möchten Sie reisen?**\n"
            "Nennen Sie ein Land, eine Stadt oder Region -- oder sagen Sie **überraschen Sie mich**."
        ),
        "it": (
            "Benvenuto su **Railbookers** -- lo specialista mondiale delle vacanze in treno.\n\n"
            "Ho accesso a **{pkg_count} viaggi ferroviari** in **50+ paesi** -- panorami alpini, treni di lusso e percorsi culturali iconici.\n\n"
            "**Dove vorresti andare?**\n"
            "Indica un paese, una città o una regione -- o di' **sorprendimi**."
        ),
        "hi": (
            "**Railbookers** में स्वागत है -- दुनिया का प्रमुख रेल वेकेशन विशेषज्ञ।\n\n"
            "मेरे पास **{pkg_count} चुनिंदा रेल यात्राएं** हैं, **50+ देशों** में -- अल्पाइन दृश्य, लक्ज़री स्लीपर ट्रेनें और प्रसिद्ध सांस्कृतिक मार्ग।\n\n"
            "**आप कहाँ जाना चाहेंगे?**\n"
            "कोई देश, शहर या क्षेत्र बताएं -- या कहें **मुझे चौंकाइए**।"
        ),
        "ja": (
            "**Railbookers**へようこそ -- 世界をリードする鉄道旅行スペシャリスト。\n\n"
            "**50か国以上**にわたる**{pkg_count}件**の厳選鉄道旅行をご用意 -- アルプスの絶景、豪華寝台列車、文化ルートなど。\n\n"
            "**どちらへ行きたいですか？**\n"
            "国名、都市名、地域名を入力 -- または**おまかせ**とどうぞ。"
        ),
        "zh": (
            "欢迎来到**Railbookers** -- 全球领先的铁路度假专家。\n\n"
            "我拥有**50+国家**的**{pkg_count}条**精选铁路旅程 -- 阿尔卑斯全景、豪华卧铺列车和标志性文化路线。\n\n"
            "**您想去哪里？**\n"
            "请输入国家、城市或地区 -- 或说**给我惊喜**。"
        ),
        "pt": (
            "Bem-vindo à **Railbookers** -- a especialista mundial em férias de trem.\n\n"
            "Tenho acesso a **{pkg_count} viagens ferroviárias** em **50+ países** -- panoramas alpinos, trens de luxo e rotas culturais icônicas.\n\n"
            "**Para onde gostaria de ir?**\n"
            "Informe um país, cidade ou região -- ou diga **surpreenda-me**."
        ),
        "ar": (
            "مرحباً بك في **Railbookers** -- الرائد العالمي في إجازات القطارات.\n\n"
            "لديّ **{pkg_count} رحلة قطار مختارة** في **50+ دولة** -- مناظر جبال الألب، قطارات النوم الفاخرة ومسارات ثقافية أيقونية.\n\n"
            "**إلى أين تود الذهاب؟**\n"
            "اذكر بلداً أو مدينة أو منطقة -- أو قل **فاجئني**."
        ),
    },

    # ---- Step questions ----
    "q_add_more": {
        "en": "Would you like to add another destination, or shall we move forward?",
        "fr": "Souhaitez-vous ajouter une autre destination, ou passons à la suite ?",
        "es": "¿Desea agregar otro destino o avanzamos?",
        "de": "Möchten Sie ein weiteres Ziel hinzufügen, oder gehen wir weiter?",
        "it": "Vuoi aggiungere un'altra destinazione o proseguiamo?",
        "hi": "क्या आप एक और गंतव्य जोड़ना चाहेंगे, या आगे बढ़ें?",
        "ja": "別の目的地を追加しますか？それとも次へ進みますか？",
        "zh": "您想添加另一个目的地，还是继续？",
        "pt": "Gostaria de adicionar outro destino ou seguimos em frente?",
        "ar": "هل تود إضافة وجهة أخرى أم ننتقل للخطوة التالية؟",
    },
    "q_travellers": {
        "en": (
            "Great. Who is joining this journey?\n\n"
            "**Solo** | **Couple** | **Family** | **Friends** | **Colleagues**\n\n"
            "Just tell me, e.g. *Couple*, *Family of 4*, *Solo traveller*"
        ),
        "fr": (
            "Parfait. Qui participe à ce voyage ?\n\n"
            "**Solo** | **Couple** | **Famille** | **Amis** | **Collègues**\n\n"
            "Dites-moi, ex. *Couple*, *Famille de 4*, *Solo*"
        ),
        "es": (
            "Perfecto. ¿Quién viaja?\n\n"
            "**Solo** | **Pareja** | **Familia** | **Amigos** | **Colegas**\n\n"
            "Dígame, ej. *Pareja*, *Familia de 4*, *Solo*"
        ),
        "de": (
            "Sehr gut. Wer reist mit?\n\n"
            "**Solo** | **Paar** | **Familie** | **Freunde** | **Kollegen**\n\n"
            "Sagen Sie mir, z.B. *Paar*, *Familie mit 4*, *Solo*"
        ),
        "it": (
            "Ottimo. Chi partecipa al viaggio?\n\n"
            "**Solo** | **Coppia** | **Famiglia** | **Amici** | **Colleghi**\n\n"
            "Dimmi, es. *Coppia*, *Famiglia di 4*, *Solo*"
        ),
        "hi": (
            "बहुत अच्छा। इस यात्रा में कौन शामिल है?\n\n"
            "**अकेले** | **जोड़ा** | **परिवार** | **दोस्त** | **सहकर्मी**\n\n"
            "बताइए, जैसे *जोड़ा*, *4 का परिवार*, *अकेले*"
        ),
        "ja": (
            "素晴らしい。どなたが参加されますか？\n\n"
            "**一人旅** | **カップル** | **家族** | **友人** | **同僚**\n\n"
            "例：*カップル*、*4人家族*、*一人旅*"
        ),
        "zh": (
            "很好。谁将参加这次旅行？\n\n"
            "**独自** | **情侣** | **家庭** | **朋友** | **同事**\n\n"
            "请告诉我，如：*情侣*、*4口之家*、*独自*"
        ),
        "pt": (
            "Ótimo. Quem participa dessa viagem?\n\n"
            "**Solo** | **Casal** | **Família** | **Amigos** | **Colegas**\n\n"
            "Diga-me, ex. *Casal*, *Família de 4*, *Solo*"
        ),
        "ar": (
            "ممتاز. من سيشارك في هذه الرحلة؟\n\n"
            "**فردي** | **زوجان** | **عائلة** | **أصدقاء** | **زملاء**\n\n"
            "أخبرني، مثل: *زوجان*، *عائلة من 4*، *فردي*"
        ),
    },
    "q_dates": {
        "en": (
            "When would you like to travel, and for how long?\n\n"
            "e.g. *June 2026, 10 days* | *Spring, 2 weeks* | *Flexible dates*\n\n"
            "I will match the best seasonal itineraries for you."
        ),
        "fr": (
            "Quand souhaitez-vous partir, et pour combien de temps ?\n\n"
            "ex. *Juin 2026, 10 jours* | *Printemps, 2 semaines* | *Dates flexibles*\n\n"
            "Je trouverai les meilleurs itinéraires saisonniers."
        ),
        "es": (
            "¿Cuándo desea viajar y por cuánto tiempo?\n\n"
            "ej. *Junio 2026, 10 días* | *Primavera, 2 semanas* | *Fechas flexibles*\n\n"
            "Encontraré los mejores itinerarios de temporada."
        ),
        "de": (
            "Wann möchten Sie reisen und für wie lange?\n\n"
            "z.B. *Juni 2026, 10 Tage* | *Frühling, 2 Wochen* | *Flexible Daten*\n\n"
            "Ich finde die besten saisonalen Reiserouten."
        ),
        "it": (
            "Quando vuoi partire e per quanto tempo?\n\n"
            "es. *Giugno 2026, 10 giorni* | *Primavera, 2 settimane* | *Date flessibili*\n\n"
            "Troverò i migliori itinerari stagionali."
        ),
        "hi": (
            "आप कब और कितने दिन यात्रा करना चाहेंगे?\n\n"
            "जैसे *जून 2026, 10 दिन* | *वसंत, 2 सप्ताह* | *लचीली तारीखें*\n\n"
            "मैं आपके लिए सर्वोत्तम मौसमी यात्रा कार्यक्रम खोजूँगा।"
        ),
        "ja": (
            "いつ、どのくらいの期間旅行しますか？\n\n"
            "例：*2026年6月、10日間* | *春、2週間* | *柔軟な日程*\n\n"
            "最適な季節のプランをお探しします。"
        ),
        "zh": (
            "您想何时出发，旅行多久？\n\n"
            "如：*2026年6月，10天* | *春季，2周* | *灵活日期*\n\n"
            "我将为您匹配最佳季节行程。"
        ),
        "pt": (
            "Quando deseja viajar e por quanto tempo?\n\n"
            "ex. *Junho 2026, 10 dias* | *Primavera, 2 semanas* | *Datas flexíveis*\n\n"
            "Encontrarei os melhores roteiros sazonais."
        ),
        "ar": (
            "متى تود السفر ولكم من الوقت؟\n\n"
            "مثل: *يونيو 2026، 10 أيام* | *الربيع، أسبوعان* | *تواريخ مرنة*\n\n"
            "سأجد لك أفضل الرحلات الموسمية."
        ),
    },
    "q_purpose": {
        "en": (
            "What kind of experience are you looking for?\n\n"
            "**Culture** | **Adventure** | **Scenic** | **Romance** | **Relaxation** | **Family** | **Luxury**\n\n"
            "This helps me match you to the right itinerary style."
        ),
        "fr": (
            "Quel type d'expérience recherchez-vous ?\n\n"
            "**Culture** | **Aventure** | **Paysages** | **Romance** | **Détente** | **Famille** | **Luxe**\n\n"
            "Cela m'aide à trouver le style d'itinéraire idéal."
        ),
        "es": (
            "¿Qué tipo de experiencia busca?\n\n"
            "**Cultura** | **Aventura** | **Paisajes** | **Romance** | **Relax** | **Familia** | **Lujo**\n\n"
            "Esto me ayuda a encontrar el itinerario perfecto."
        ),
        "de": (
            "Welche Art von Erlebnis suchen Sie?\n\n"
            "**Kultur** | **Abenteuer** | **Landschaft** | **Romantik** | **Entspannung** | **Familie** | **Luxus**\n\n"
            "So finde ich den passenden Reisestil."
        ),
        "it": (
            "Che tipo di esperienza cerchi?\n\n"
            "**Cultura** | **Avventura** | **Panorami** | **Romanticismo** | **Relax** | **Famiglia** | **Lusso**\n\n"
            "Questo mi aiuta a trovare lo stile di viaggio giusto."
        ),
        "hi": (
            "आप किस तरह का अनुभव चाहते हैं?\n\n"
            "**संस्कृति** | **रोमांच** | **प्राकृतिक दृश्य** | **रोमांस** | **आराम** | **परिवार** | **लक्ज़री**\n\n"
            "इससे मैं आपके लिए सही यात्रा शैली खोज सकूँगा।"
        ),
        "ja": (
            "どんな体験をお探しですか？\n\n"
            "**文化** | **冒険** | **絶景** | **ロマンス** | **リラックス** | **家族** | **ラグジュアリー**\n\n"
            "最適な旅のスタイルをご提案します。"
        ),
        "zh": (
            "您想要什么样的体验？\n\n"
            "**文化** | **探险** | **风景** | **浪漫** | **休闲** | **家庭** | **奢华**\n\n"
            "这将帮助我匹配最适合您的行程风格。"
        ),
        "pt": (
            "Que tipo de experiência procura?\n\n"
            "**Cultura** | **Aventura** | **Paisagens** | **Romance** | **Relaxamento** | **Família** | **Luxo**\n\n"
            "Isso me ajuda a encontrar o estilo de roteiro ideal."
        ),
        "ar": (
            "ما نوع التجربة التي تبحث عنها؟\n\n"
            "**ثقافة** | **مغامرة** | **مناظر** | **رومانسية** | **استرخاء** | **عائلة** | **فخامة**\n\n"
            "هذا يساعدني في إيجاد أسلوب الرحلة المناسب."
        ),
    },
    "q_occasion": {
        "en": (
            "Are you celebrating a special occasion?\n\n"
            "**Anniversary** | **Honeymoon** | **Birthday** | **Retirement** | **Just for fun**\n\n"
            "I can tailor recommendations to make it unforgettable."
        ),
        "fr": (
            "Célébrez-vous une occasion spéciale ?\n\n"
            "**Anniversaire** | **Lune de miel** | **Fête** | **Retraite** | **Pour le plaisir**\n\n"
            "Je personnaliserai les recommandations pour un moment inoubliable."
        ),
        "es": (
            "¿Celebra alguna ocasión especial?\n\n"
            "**Aniversario** | **Luna de miel** | **Cumpleaños** | **Jubilación** | **Por diversión**\n\n"
            "Personalizaré las recomendaciones para hacerla inolvidable."
        ),
        "de": (
            "Feiern Sie einen besonderen Anlass?\n\n"
            "**Jubiläum** | **Flitterwochen** | **Geburtstag** | **Ruhestand** | **Einfach so**\n\n"
            "Ich kann die Empfehlungen für ein unvergessliches Erlebnis anpassen."
        ),
        "it": (
            "Festeggi un'occasione speciale?\n\n"
            "**Anniversario** | **Luna di miele** | **Compleanno** | **Pensionamento** | **Per divertimento**\n\n"
            "Posso personalizzare i suggerimenti per renderlo indimenticabile."
        ),
        "hi": (
            "कोई विशेष अवसर है?\n\n"
            "**सालगिरह** | **हनीमून** | **जन्मदिन** | **सेवानिवृत्ति** | **बस मज़े के लिए**\n\n"
            "मैं इसे यादगार बनाने के लिए सिफारिशें अनुकूलित करूँगा।"
        ),
        "ja": (
            "特別な記念日ですか？\n\n"
            "**記念日** | **ハネムーン** | **誕生日** | **退職** | **楽しみのため**\n\n"
            "忘れられない旅にするためのご提案をいたします。"
        ),
        "zh": (
            "有特别的庆祝场合吗？\n\n"
            "**周年纪念** | **蜜月** | **生日** | **退休** | **纯粹享乐**\n\n"
            "我会为您定制难忘的旅程推荐。"
        ),
        "pt": (
            "Celebra alguma ocasião especial?\n\n"
            "**Aniversário** | **Lua de mel** | **Aniversário** | **Aposentadoria** | **Só por diversão**\n\n"
            "Posso personalizar as recomendações para torná-la inesquecível."
        ),
        "ar": (
            "هل تحتفل بمناسبة خاصة؟\n\n"
            "**ذكرى زواج** | **شهر عسل** | **عيد ميلاد** | **تقاعد** | **للمتعة فقط**\n\n"
            "يمكنني تخصيص التوصيات لجعلها لا تُنسى."
        ),
    },
    "q_hotel": {
        "en": (
            "What level of accommodation do you prefer?\n\n"
            "**Luxury** -- five-star, world-class (e.g. Ritz-Carlton, Four Seasons)\n"
            "**Premium** -- upscale, four-star (e.g. Marriott, Sheraton)\n"
            "**Value** -- comfortable, well-rated (e.g. Holiday Inn, Best Western)\n\n"
            "Or say *No preference* and I will show a balanced range."
        ),
        "fr": (
            "Quel niveau d'hébergement préférez-vous ?\n\n"
            "**Luxe** (5 étoiles) | **Premium** (4 étoiles) | **Confort** (confortable & bien noté)\n\n"
            "Ou dites *Pas de préférence* pour une sélection équilibrée."
        ),
        "es": (
            "¿Qué nivel de alojamiento prefiere?\n\n"
            "**Lujo** (5 estrellas) | **Premium** (4 estrellas) | **Valor** (cómodo y bien valorado)\n\n"
            "O diga *Sin preferencia* para ver una selección equilibrada."
        ),
        "de": (
            "Welches Unterkunftsniveau bevorzugen Sie?\n\n"
            "**Luxus** (5 Sterne) | **Premium** (4 Sterne) | **Komfort** (komfortabel & gut bewertet)\n\n"
            "Oder sagen Sie *Keine Präferenz* für eine ausgewogene Auswahl."
        ),
        "it": (
            "Che livello di alloggio preferisci?\n\n"
            "**Lusso** (5 stelle) | **Premium** (4 stelle) | **Comfort** (comodo & ben valutato)\n\n"
            "Oppure dì *Nessuna preferenza* per una selezione bilanciata."
        ),
        "hi": (
            "आप किस स्तर का आवास पसंद करते हैं?\n\n"
            "**लक्ज़री** (5-स्टार, विश्व-स्तरीय) | **प्रीमियम** (4-स्टार) | **वैल्यू** (आरामदायक और उच्च रेटिंग)\n\n"
            "या कहें *कोई प्राथमिकता नहीं* -- संतुलित विकल्प दिखाऊंगा।"
        ),
        "ja": (
            "宿泊のレベルはいかがですか？\n\n"
            "**ラグジュアリー** (5つ星) | **プレミアム** (4つ星) | **バリュー** (快適&高評価)\n\n"
            "*こだわりなし*でバランスの良い選択肢をご提案します。"
        ),
        "zh": (
            "您偏好什么级别的住宿？\n\n"
            "**奢华** (5星级) | **高级** (4星级) | **舒适** (舒适且高评分)\n\n"
            "或说*无偏好*，我将展示均衡选择。"
        ),
        "pt": (
            "Que nível de acomodação prefere?\n\n"
            "**Luxo** (5 estrelas) | **Premium** (4 estrelas) | **Valor** (confortável & bem avaliado)\n\n"
            "Ou diga *Sem preferência* para ver uma seleção balanceada."
        ),
        "ar": (
            "ما مستوى الإقامة الذي تفضله؟\n\n"
            "**فاخر** (5 نجوم) | **مميز** (4 نجوم) | **مريح** (مريح وعالي التقييم)\n\n"
            "أو قل *لا تفضيل* لعرض مجموعة متوازنة."
        ),
    },
    "q_rail": {
        "en": (
            "Have you taken a rail vacation before?\n\n"
            "**First time** | **A few trips** | **Seasoned traveller**\n\n"
            "This helps me recommend routes suited to your experience level."
        ),
        "fr": (
            "Avez-vous déjà pris des vacances en train ?\n\n"
            "**Première fois** | **Quelques voyages** | **Voyageur aguerri**\n\n"
            "Cela m'aide à recommander des itinéraires adaptés à votre niveau."
        ),
        "es": (
            "¿Ha tomado vacaciones en tren antes?\n\n"
            "**Primera vez** | **Algunos viajes** | **Viajero experimentado**\n\n"
            "Esto me ayuda a recomendar rutas según su experiencia."
        ),
        "de": (
            "Haben Sie schon einmal eine Bahnreise gemacht?\n\n"
            "**Erstes Mal** | **Einige Reisen** | **Erfahrener Reisender**\n\n"
            "So kann ich passende Routen für Ihr Erfahrungsniveau empfehlen."
        ),
        "it": (
            "Hai mai fatto una vacanza in treno?\n\n"
            "**Prima volta** | **Qualche viaggio** | **Viaggiatore esperto**\n\n"
            "Questo mi aiuterà a suggerire percorsi adatti alla tua esperienza."
        ),
        "hi": (
            "क्या आपने पहले रेल यात्रा की है?\n\n"
            "**पहली बार** | **कुछ यात्राएं** | **अनुभवी यात्री**\n\n"
            "इससे मैं आपके अनुभव स्तर के अनुसार मार्ग सुझा सकूँगा।"
        ),
        "ja": (
            "鉄道旅行の経験はありますか？\n\n"
            "**初めて** | **数回** | **ベテラン**\n\n"
            "経験レベルに合った最適なルートをご提案します。"
        ),
        "zh": (
            "您之前参加过火车旅行吗？\n\n"
            "**第一次** | **几次** | **资深旅客**\n\n"
            "这帮助我推荐适合您经验水平的路线。"
        ),
        "pt": (
            "Já fez férias de trem antes?\n\n"
            "**Primeira vez** | **Algumas viagens** | **Viajante experiente**\n\n"
            "Isso me ajuda a recomendar rotas adequadas ao seu nível de experiência."
        ),
        "ar": (
            "هل سبق لك قضاء إجازة بالقطار؟\n\n"
            "**أول مرة** | **بضع رحلات** | **مسافر متمرس**\n\n"
            "هذا يساعدني في اقتراح مسارات تناسب مستوى خبرتك."
        ),
    },
    "q_budget": {
        "en": (
            "Almost there. Any budget per person or special requirements?\n\n"
            "e.g. *£5,000 per person*, *No limit*, *Wheelchair accessible*\n\n"
            "Or say **Find my trips** and I will search now."
        ),
        "fr": (
            "Presque terminé. Budget par personne ou besoins particuliers ?\n\n"
            "ex. *5 000 € par personne*, *Pas de limite*, *Accès fauteuil roulant*\n\n"
            "Ou dites **Trouver mes voyages** pour lancer la recherche."
        ),
        "es": (
            "Casi listo. ¿Presupuesto por persona o necesidades especiales?\n\n"
            "ej. *5.000 € por persona*, *Sin límite*, *Acceso para silla de ruedas*\n\n"
            "O diga **Buscar mis viajes** para buscar ahora."
        ),
        "de": (
            "Fast fertig. Budget pro Person oder besondere Anforderungen?\n\n"
            "z.B. *5.000 € pro Person*, *Kein Limit*, *Rollstuhlgerecht*\n\n"
            "Oder sagen Sie **Meine Reisen finden** um jetzt zu suchen."
        ),
        "it": (
            "Quasi finito. Budget a persona o esigenze particolari?\n\n"
            "es. *5.000 € a persona*, *Nessun limite*, *Accessibile in sedia a rotelle*\n\n"
            "Oppure dì **Trova i miei viaggi** per cercare ora."
        ),
        "hi": (
            "बस एक आखिरी बात। प्रति व्यक्ति बजट या कोई विशेष ज़रूरतें?\n\n"
            "जैसे *₹3,00,000 प्रति व्यक्ति*, *कोई सीमा नहीं*, *व्हीलचेयर सुलभ*\n\n"
            "या बस कहें **मेरी यात्राएं खोजें** अभी खोजने के लिए।"
        ),
        "ja": (
            "あと少しです。お一人様のご予算や特別なご要望は？\n\n"
            "例：*¥500,000*、*制限なし*、*車椅子対応*\n\n"
            "または**旅を探す**で今すぐ検索。"
        ),
        "zh": (
            "快完成了。每人预算或特殊需求？\n\n"
            "如：*每人¥30,000*、*无限制*、*轮椅无障碍*\n\n"
            "或输入**查找我的旅程**立即搜索。"
        ),
        "pt": (
            "Quase lá. Orçamento por pessoa ou necessidades especiais?\n\n"
            "ex. *€5.000 por pessoa*, *Sem limite*, *Acessível para cadeira de rodas*\n\n"
            "Ou diga **Encontrar minhas viagens** para pesquisar agora."
        ),
        "ar": (
            "اقتربنا. ميزانية للشخص أو متطلبات خاصة؟\n\n"
            "مثل: *5,000 جنيه للشخص*، *بلا حد*، *وصول كرسي متحرك*\n\n"
            "أو قل **ابحث عن رحلاتي** للبحث الآن."
        ),
    },

    # ---- Key phrases ----
    "outstanding_choice": {
        "en": "Excellent choice",
        "fr": "Excellent choix",
        "es": "Excelente elección",
        "de": "Hervorragende Wahl",
        "it": "Scelta eccellente",
        "hi": "उत्कृष्ट चुनाव",
        "ja": "素晴らしい選択",
        "zh": "绝佳选择",
        "pt": "Escolha excelente",
        "ar": "اختيار ممتاز",
    },
    "searching_for": {
        "en": "Perfect -- {dest} locked in.",
        "fr": "Parfait -- {dest} confirmé.",
        "es": "Perfecto -- {dest} confirmado.",
        "de": "Perfekt -- {dest} bestätigt.",
        "it": "Perfetto -- {dest} confermato.",
        "hi": "बिल्कुल सही -- {dest} तय हो गया।",
        "ja": "完璧 -- {dest}を確定しました。",
        "zh": "完美 -- {dest}已确认。",
        "pt": "Perfeito -- {dest} confirmado.",
        "ar": "ممتاز -- تم تأكيد {dest}.",
    },
    "here_is_search": {
        "en": "Your journey brief:",
        "fr": "Votre résumé de voyage :",
        "es": "Su resumen de viaje:",
        "de": "Ihre Reiseübersicht:",
        "it": "Il tuo riepilogo di viaggio:",
        "hi": "आपका यात्रा सारांश:",
        "ja": "旅の概要：",
        "zh": "您的旅程摘要：",
        "pt": "Seu resumo de viagem:",
        "ar": "ملخص رحلتك:",
    },
    "here_is_searched": {
        "en": "Search complete. Here is your brief:",
        "fr": "Recherche terminée. Voici votre résumé :",
        "es": "Búsqueda completada. Aquí está su resumen:",
        "de": "Suche abgeschlossen. Hier Ihre Übersicht:",
        "it": "Ricerca completata. Ecco il riepilogo:",
        "hi": "खोज पूर्ण। यहाँ आपका सारांश:",
        "ja": "検索完了。概要はこちら：",
        "zh": "搜索完成。以下是您的摘要：",
        "pt": "Pesquisa concluída. Aqui está seu resumo:",
        "ar": "اكتمل البحث. إليك ملخصك:",
    },
    "your_recs": {
        "en": "Your personally curated recommendations:",
        "fr": "Vos recommandations sur mesure :",
        "es": "Sus recomendaciones a medida:",
        "de": "Ihre maßgeschneiderten Empfehlungen:",
        "it": "Le tue raccomandazioni su misura:",
        "hi": "आपकी विशेष रूप से चुनी गई सिफारिशें:",
        "ja": "あなた専用のおすすめ：",
        "zh": "为您精心挑选的推荐：",
        "pt": "Suas recomendações sob medida:",
        "ar": "توصياتك المصممة خصيصاً:",
    },
    "no_matches": {
        "en": "No exact match for these criteria. Try adjusting the duration, broadening the destination, or relaxing filters.\n\nAlternatively, **speak with an advisor** and we will craft a bespoke itinerary just for you.",
        "fr": "Aucun résultat exact. Ajustez la durée, élargissez la destination ou **parlez à un conseiller** pour un itinéraire sur mesure.",
        "es": "Sin resultados exactos. Ajuste la duración, amplíe el destino o **hable con un asesor** para un itinerario personalizado.",
        "de": "Kein exakter Treffer. Passen Sie die Dauer an, erweitern Sie das Ziel oder **sprechen Sie mit einem Berater** für eine maßgeschneiderte Reise.",
        "it": "Nessun risultato esatto. Regola la durata, amplia la destinazione o **parla con un consulente** per un itinerario su misura.",
        "hi": "इन मानदंडों से कोई सटीक मिलान नहीं। अवधि बदलें, गंतव्य बढ़ाएं, या **सलाहकार से बात करें**।",
        "ja": "この条件での一致なし。期間を変更、目的地を広げるか、**アドバイザーに相談**ください。",
        "zh": "无精确匹配。调整时长、扩大目的地，或**咨询顾问**为您定制行程。",
        "pt": "Sem resultados exatos. Ajuste a duração, amplie o destino ou **fale com um consultor** para um roteiro personalizado.",
        "ar": "لا نتائج مطابقة. عدّل المدة، وسّع الوجهة، أو **تحدث مع مستشار** لرحلة مخصصة.",
    },
    "does_look_right": {
        "en": "Does everything look correct? Hit **Search now** to find your matches, or tell me what to adjust.",
        "fr": "Tout est correct ? Cliquez **Rechercher** ou dites-moi quoi ajuster.",
        "es": "¿Todo correcto? Pulse **Buscar ahora** o dígame qué ajustar.",
        "de": "Alles korrekt? Klicken Sie **Jetzt suchen** oder sagen Sie mir, was angepasst werden soll.",
        "it": "Tutto corretto? Premi **Cerca ora** o dimmi cosa modificare.",
        "hi": "सब सही है? **अभी खोजें** दबाएं या बताएं क्या बदलना है।",
        "ja": "すべてよろしいですか？**今すぐ検索**か、変更点をお知らせください。",
        "zh": "一切正确吗？点击**立即搜索**或告诉我需要调整什么。",
        "pt": "Tudo correto? Clique **Pesquisar agora** ou me diga o que ajustar.",
        "ar": "هل كل شيء صحيح؟ اضغط **ابحث الآن** أو أخبرني بالتعديلات.",
    },

    # ---- Placeholders ----
    "ph_destination": {
        "en": "Type a country, city, or region...",
        "fr": "Saisissez un pays, une ville ou une région...",
        "es": "Escriba un país, ciudad o región...",
        "de": "Land, Stadt oder Region eingeben...",
        "it": "Inserisci un paese, una città o una regione...",
        "hi": "कोई देश, शहर या क्षेत्र लिखें...",
        "ja": "国名、都市名、地域名を入力...",
        "zh": "输入国家、城市或地区...",
        "pt": "Digite um país, cidade ou região...",
        "ar": "اكتب بلد أو مدينة أو منطقة...",
    },
    "ph_travellers": {
        "en": "e.g. 2 adults and 1 child, couple, solo...",
        "fr": "ex. 2 adultes et 1 enfant, couple, seul...",
        "es": "ej. 2 adultos y 1 niño, pareja, solo...",
        "de": "z.B. 2 Erwachsene und 1 Kind, Paar, allein...",
        "it": "es. 2 adulti e 1 bambino, coppia, solo...",
        "hi": "जैसे 2 वयस्क और 1 बच्चा, जोड़ा, अकेला...",
        "ja": "例：大人2人と子供1人、カップル、一人旅...",
        "zh": "如：2个大人和1个孩子、情侣、独自旅行...",
        "pt": "ex. 2 adultos e 1 criança, casal, sozinho...",
        "ar": "مثل: شخصان بالغان وطفل، زوجان، بمفردي...",
    },
    "ph_dates": {
        "en": "e.g. June 2026, 10 days, flexible...",
        "fr": "ex. Juin 2026, 10 jours, flexible...",
        "es": "ej. Junio 2026, 10 días, flexible...",
        "de": "z.B. Juni 2026, 10 Tage, flexibel...",
        "it": "es. Giugno 2026, 10 giorni, flessibile...",
        "hi": "जैसे जून 2026, 10 दिन, लचीला...",
        "ja": "例：2026年6月、10日間、柔軟...",
        "zh": "如：2026年6月，10天，灵活...",
        "pt": "ex. Junho 2026, 10 dias, flexível...",
        "ar": "مثل: يونيو 2026، 10 أيام، مرن...",
    },
}

# ---------------------------------------------------------------------------
# List translations  (suggestions / button labels)
# ---------------------------------------------------------------------------
_TL = {
    "flexible_dates": {
        "en": ["Flexible dates"],
        "fr": ["Dates flexibles"],
        "es": ["Fechas flexibles"],
        "de": ["Flexible Daten"],
        "it": ["Date flessibili"],
        "hi": ["लचीली तारीखें"],
        "ja": ["柔軟な日程"],
        "zh": ["灵活日期"],
        "pt": ["Datas flexíveis"],
        "ar": ["تواريخ مرنة"],
    },
    "no_occasion": {
        "en": ["No special occasion"],
        "fr": ["Pas d'occasion spéciale"],
        "es": ["Sin ocasión especial"],
        "de": ["Kein besonderer Anlass"],
        "it": ["Nessuna occasione speciale"],
        "hi": ["कोई विशेष अवसर नहीं"],
        "ja": ["特別な機会はなし"],
        "zh": ["没有特别场合"],
        "pt": ["Sem ocasião especial"],
        "ar": ["لا مناسبة خاصة"],
    },
    "budget_actions": {
        "en": ["Find my perfect trips", "No budget limit"],
        "fr": ["Trouver mes voyages parfaits", "Pas de limite de budget"],
        "es": ["Encontrar mis viajes perfectos", "Sin límite de presupuesto"],
        "de": ["Meine perfekten Reisen finden", "Kein Budgetlimit"],
        "it": ["Trova i miei viaggi perfetti", "Nessun limite di budget"],
        "hi": ["मेरी सही यात्राएं खोजें", "कोई बजट सीमा नहीं"],
        "ja": ["理想の旅を見つける", "予算制限なし"],
        "zh": ["找到我的完美旅行", "无预算限制"],
        "pt": ["Encontrar minhas viagens perfeitas", "Sem limite de orçamento"],
        "ar": ["ابحث عن رحلاتي المثالية", "بلا حد للميزانية"],
    },
    "post_rec": {
        "en": ["Plan another trip", "Modify preferences", "Speak with an advisor"],
        "fr": ["Planifier un autre voyage", "Modifier les préférences", "Parler à un conseiller"],
        "es": ["Planificar otro viaje", "Modificar preferencias", "Hablar con un asesor"],
        "de": ["Weitere Reise planen", "Einstellungen ändern", "Mit einem Berater sprechen"],
        "it": ["Pianifica un altro viaggio", "Modifica preferenze", "Parla con un consulente"],
        "hi": ["एक और यात्रा की योजना बनाएं", "प्राथमिकताएं बदलें", "सलाहकार से बात करें"],
        "ja": ["別の旅を計画", "設定を変更", "アドバイザーに相談"],
        "zh": ["计划另一次旅行", "修改偏好", "与顾问交谈"],
        "pt": ["Planejar outra viagem", "Modificar preferências", "Falar com um consultor"],
        "ar": ["التخطيط لرحلة أخرى", "تعديل التفضيلات", "التحدث مع مستشار"],
    },
    "confirm_search": {
        "en": ["Search now", "Modify preferences"],
        "fr": ["Rechercher maintenant", "Modifier les préférences"],
        "es": ["Buscar ahora", "Modificar preferencias"],
        "de": ["Jetzt suchen", "Einstellungen ändern"],
        "it": ["Cerca ora", "Modifica preferenze"],
        "hi": ["अभी खोजें", "प्राथमिकताएं बदलें"],
        "ja": ["今すぐ検索", "設定を変更"],
        "zh": ["立即搜索", "修改偏好"],
        "pt": ["Pesquisar agora", "Modificar preferências"],
        "ar": ["ابحث الآن", "تعديل التفضيلات"],
    },
}

# Alias for i18n module compatibility
_TRANSLATIONS = _T
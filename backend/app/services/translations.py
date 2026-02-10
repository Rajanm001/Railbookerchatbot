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
            "Welcome to **Railbookers**. I will find your perfect rail vacation from our curated collection of expert-designed journeys across 50+ countries.\n\n"
            "**Where would you like to go?**\n"
            "Type a country, city, or region below."
        ),
        "fr": (
            "Bienvenue chez **Railbookers**. Je trouverai votre voyage en train idéal parmi notre collection de voyages conçus par des experts dans plus de 50 pays.\n\n"
            "**Où souhaitez-vous aller ?**\n"
            "Saisissez un pays, une ville ou une région ci-dessous."
        ),
        "es": (
            "Bienvenido a **Railbookers**. Encontraré su vacación en tren perfecta de nuestra colección de viajes diseñados por expertos en más de 50 países.\n\n"
            "**¿Adónde le gustaría ir?**\n"
            "Escriba un país, ciudad o región a continuación."
        ),
        "de": (
            "Willkommen bei **Railbookers**. Ich finde Ihren perfekten Bahnurlaub aus unserer Kollektion von Experten-Reisen in über 50 Ländern.\n\n"
            "**Wohin möchten Sie reisen?**\n"
            "Geben Sie ein Land, eine Stadt oder eine Region ein."
        ),
        "it": (
            "Benvenuto su **Railbookers**. Troverò la tua vacanza in treno perfetta dalla nostra collezione di viaggi creati da esperti in oltre 50 paesi.\n\n"
            "**Dove vorresti andare?**\n"
            "Inserisci un paese, una città o una regione."
        ),
        "hi": (
            "**Railbookers** में आपका स्वागत है। मैं 50+ देशों में विशेषज्ञ-डिज़ाइन की गई यात्राओं के हमारे संग्रह से आपकी सही रेल छुट्टी खोजूँगा।\n\n"
            "**आप कहाँ जाना चाहेंगे?**\n"
            "नीचे कोई देश, शहर या क्षेत्र लिखें।"
        ),
        "ja": (
            "**Railbookers**へようこそ。50か国以上のエキスパート厳選コレクションから、最適な鉄道旅行をお探しします。\n\n"
            "**どちらへ旅行されたいですか？**\n"
            "国名、都市名、地域名を入力してください。"
        ),
        "zh": (
            "欢迎来到**Railbookers**。我将从覆盖50多个国家的专家精选系列中为您找到完美的铁路度假。\n\n"
            "**您想去哪里？**\n"
            "请在下方输入国家、城市或地区。"
        ),
        "pt": (
            "Bem-vindo à **Railbookers**. Encontrarei suas férias de trem perfeitas em nossa coleção de viagens projetadas por especialistas em mais de 50 países.\n\n"
            "**Para onde gostaria de ir?**\n"
            "Digite um país, cidade ou região abaixo."
        ),
        "ar": (
            "مرحباً بكم في **Railbookers**. سأجد لكم إجازة القطار المثالية من مجموعتنا المختارة بعناية في أكثر من 50 دولة.\n\n"
            "**إلى أين تود الذهاب؟**\n"
            "اكتب اسم بلد أو مدينة أو منطقة أدناه."
        ),
    },

    # ---- Step questions ----
    "q_add_more": {
        "en": "Would you like to add another destination, or shall we continue?",
        "fr": "Souhaitez-vous ajouter une autre destination, ou continuons-nous ?",
        "es": "¿Le gustaría añadir otro destino o continuamos?",
        "de": "Möchten Sie ein weiteres Reiseziel hinzufügen, oder fahren wir fort?",
        "it": "Vuoi aggiungere un'altra destinazione o continuiamo?",
        "hi": "क्या आप एक और गंतव्य जोड़ना चाहेंगे, या आगे बढ़ें?",
        "ja": "別の目的地を追加しますか？それとも次に進みますか？",
        "zh": "您想添加另一个目的地，还是继续？",
        "pt": "Gostaria de adicionar outro destino ou continuamos?",
        "ar": "هل تود إضافة وجهة أخرى، أم نستمر؟",
    },
    "q_travellers": {
        "en": (
            "Who will be travelling with you, and how many guests in total?\n"
            "For example: couple, 2 adults and 2 children, solo, group of 6."
        ),
        "fr": (
            "Qui voyagera avec vous et combien de personnes au total ?\n"
            "Par exemple : moi et ma femme, 2 adultes et 2 enfants, seul, groupe de 6 amis."
        ),
        "es": (
            "¿Quién viajará con usted y cuántas personas en total?\n"
            "Por ejemplo: mi esposa y yo, 2 adultos y 2 niños, solo, grupo de 6 amigos."
        ),
        "de": (
            "Wer reist mit Ihnen und wie viele Gäste insgesamt?\n"
            "Zum Beispiel: meine Frau und ich, 2 Erwachsene und 2 Kinder, allein, Gruppe von 6 Freunden."
        ),
        "it": (
            "Chi viaggerà con te e quante persone in tutto?\n"
            "Per esempio: io e mia moglie, 2 adulti e 2 bambini, da solo, gruppo di 6 amici."
        ),
        "hi": (
            "आपके साथ कौन यात्रा करेगा और कुल कितने लोग?\n"
            "उदाहरण: मैं और मेरी पत्नी, 2 वयस्क और 2 बच्चे, अकेला, 6 दोस्तों का समूह।"
        ),
        "ja": (
            "どなたとご一緒ですか？合計何名ですか？\n"
            "例：夫婦2人、大人2人と子供2人、一人旅、友人6人グループ"
        ),
        "zh": (
            "谁将与您同行，共几人？\n"
            "例如：我和妻子、2个大人和2个孩子、独自旅行、6个朋友的团队。"
        ),
        "pt": (
            "Quem viajará com você e quantas pessoas no total?\n"
            "Por exemplo: eu e minha esposa, 2 adultos e 2 crianças, sozinho, grupo de 6 amigos."
        ),
        "ar": (
            "من سيسافر معك وكم عدد الأشخاص إجمالاً؟\n"
            "مثال: أنا وزوجتي، شخصان بالغان وطفلان، بمفردي، مجموعة من 6 أصدقاء."
        ),
    },
    "q_dates": {
        "en": (
            "When would you like to travel, and for how long?\n"
            "Use the calendar below or type something like 'June 2026, 10 days'."
        ),
        "fr": (
            "Quand souhaitez-vous voyager et pour combien de temps ?\n"
            "Sélectionnez les dates ci-dessous ou tapez par exemple 'Juin 2026, 10 jours'."
        ),
        "es": (
            "¿Cuándo le gustaría viajar y por cuánto tiempo?\n"
            "Seleccione fechas del calendario o escriba algo como 'Junio 2026, 10 días'."
        ),
        "de": (
            "Wann möchten Sie reisen und wie lange?\n"
            "Wählen Sie Daten im Kalender oder schreiben Sie z.B. 'Juni 2026, 10 Tage'."
        ),
        "it": (
            "Quando vorresti viaggiare e per quanto tempo?\n"
            "Seleziona le date dal calendario o scrivi ad esempio 'Giugno 2026, 10 giorni'."
        ),
        "hi": (
            "आप कब यात्रा करना चाहेंगे और कितने दिन?\n"
            "नीचे कैलेंडर से तारीखें चुनें या लिखें जैसे 'जून 2026, 10 दिन'।"
        ),
        "ja": (
            "いつ頃、どのくらいの期間旅行されたいですか？\n"
            "カレンダーから日付を選ぶか、「2026年6月、10日間」のように入力してください。"
        ),
        "zh": (
            "您想什么时候旅行，旅行多长时间？\n"
            "从下方日历中选择日期，或输入如'2026年6月, 10天'。"
        ),
        "pt": (
            "Quando gostaria de viajar e por quanto tempo?\n"
            "Selecione datas no calendário ou digite algo como 'Junho 2026, 10 dias'."
        ),
        "ar": (
            "متى تود السفر وكم المدة؟\n"
            "اختر التواريخ من التقويم أو اكتب مثل 'يونيو 2026، 10 أيام'."
        ),
    },
    "q_purpose": {
        "en": (
            "What kind of experience are you looking for?\n\n"
            "_e.g. scenic journeys, famous trains, culture & heritage, adventure, luxury, romance -- or describe in your own words._"
        ),
        "fr": (
            "Quel type d'expérience recherchez-vous ?\n\n"
            "_ex. voyages panoramiques, trains célèbres, culture, aventure, luxe, romance -- ou décrivez avec vos propres mots._"
        ),
        "es": (
            "¿Qué tipo de experiencia busca?\n\n"
            "_ej. viajes panorámicos, trenes famosos, cultura, aventura, lujo, romance -- o describa con sus propias palabras._"
        ),
        "de": (
            "Welche Art von Erlebnis suchen Sie?\n\n"
            "_z.B. malerische Reisen, berühmte Züge, Kultur, Abenteuer, Luxus, Romantik -- oder beschreiben Sie es in Ihren eigenen Worten._"
        ),
        "it": (
            "Che tipo di esperienza state cercando?\n\n"
            "_es. viaggi panoramici, treni famosi, cultura, avventura, lusso, romanticismo -- o descrivete con le vostre parole._"
        ),
        "hi": (
            "आप किस प्रकार का अनुभव चाहते हैं?\n\n"
            "_जैसे दर्शनीय यात्राएं, प्रसिद्ध ट्रेनें, संस्कृति, साहसिक, लग्ज़री, रोमांस -- या अपने शब्दों में बताएं।_"
        ),
        "ja": (
            "どのような体験をお探しですか？\n\n"
            "_例：絶景の旅、有名な列車、文化体験、冒険、ラグジュアリー、ロマンス -- またはご自身の言葉でお書きください。_"
        ),
        "zh": (
            "您在寻找什么样的体验？\n\n"
            "_例如：风景之旅、著名列车、文化探索、冒险、豪华、浪漫 -- 或用您自己的话描述。_"
        ),
        "pt": (
            "Que tipo de experiência você procura?\n\n"
            "_ex. viagens panorâmicas, trens famosos, cultura, aventura, luxo, romance -- ou descreva com suas próprias palavras._"
        ),
        "ar": (
            "ما نوع التجربة التي تبحث عنها؟\n\n"
            "_مثال: رحلات ذات مناظر خلابة، قطارات شهيرة، ثقافة، مغامرة، فخامة، رومانسية -- أو صف بكلماتك الخاصة._"
        ),
    },
    "q_occasion": {
        "en": "Are you celebrating a special occasion?\n(e.g. Birthday, Anniversary, Honeymoon, Graduation, or just for fun)",
        "fr": "Célébrez-vous une occasion spéciale ?\n(ex. Anniversaire, Lune de miel, Remise de diplôme, ou juste pour le plaisir)",
        "es": "¿Está celebrando una ocasión especial?\n(ej. Cumpleaños, Aniversario, Luna de miel, Graduación, o simplemente por diversión)",
        "de": "Feiern Sie einen besonderen Anlass?\n(z.B. Geburtstag, Jubiläum, Flitterwochen, Abschluss, oder einfach zum Spaß)",
        "it": "State celebrando un'occasione speciale?\n(es. Compleanno, Anniversario, Luna di miele, Laurea, o semplicemente per divertimento)",
        "hi": "क्या आप कोई विशेष अवसर मना रहे हैं?\n(जैसे जन्मदिन, सालगिरह, हनीमून, स्नातक, या बस मज़े के लिए)",
        "ja": "特別なお祝いはありますか？\n（例：誕生日、記念日、ハネムーン、卒業、または楽しみのため）",
        "zh": "您是否在庆祝什么特别的场合？\n（如：生日、纪念日、蜜月、毕业、或只是为了乐趣）",
        "pt": "Você está comemorando alguma ocasião especial?\n(ex. Aniversário, Lua de mel, Formatura, ou apenas por diversão)",
        "ar": "هل تحتفلون بمناسبة خاصة؟\n(مثل: عيد ميلاد، ذكرى زواج، شهر عسل، تخرج، أو فقط للمتعة)",
    },
    "q_hotel": {
        "en": (
            "What type of hotels do you prefer?\n\n"
            "  - Luxury -- Five-star: Ritz-Carlton, Four Seasons\n"
            "  - Premium -- Upscale: Marriott, Hilton\n"
            "  - Value -- Comfortable: Holiday Inn, Best Western"
        ),
        "fr": (
            "Quel type d'hôtels préférez-vous ?\n\n"
            "  - Luxe -- Cinq étoiles : Ritz-Carlton, Four Seasons\n"
            "  - Premium -- Haut de gamme : Marriott, Hilton\n"
            "  - Économique -- Confortable : Holiday Inn, Best Western"
        ),
        "es": (
            "¿Qué tipo de hoteles prefiere?\n\n"
            "  - Lujo -- Cinco estrellas: Ritz-Carlton, Four Seasons\n"
            "  - Premium -- De alta gama: Marriott, Hilton\n"
            "  - Económico -- Cómodo: Holiday Inn, Best Western"
        ),
        "de": (
            "Welche Art von Hotels bevorzugen Sie?\n\n"
            "  - Luxus -- Fünf Sterne: Ritz-Carlton, Four Seasons\n"
            "  - Premium -- Gehoben: Marriott, Hilton\n"
            "  - Komfort -- Komfortabel: Holiday Inn, Best Western"
        ),
        "it": (
            "Che tipo di hotel preferisci?\n\n"
            "  - Lusso -- Cinque stelle: Ritz-Carlton, Four Seasons\n"
            "  - Premium -- Di alta classe: Marriott, Hilton\n"
            "  - Economico -- Confortevole: Holiday Inn, Best Western"
        ),
        "hi": (
            "आप किस प्रकार के होटल पसंद करते हैं?\n\n"
            "  - लग्ज़री -- पाँच सितारा: Ritz-Carlton, Four Seasons\n"
            "  - प्रीमियम -- उच्च श्रेणी: Marriott, Hilton\n"
            "  - वैल्यू -- आरामदायक: Holiday Inn, Best Western"
        ),
        "ja": (
            "どのタイプのホテルをご希望ですか？\n\n"
            "  - ラグジュアリー -- 五つ星：リッツ・カールトン、フォーシーズンズ\n"
            "  - プレミアム -- 高級：マリオット、ヒルトン\n"
            "  - バリュー -- 快適：ホリデイ・イン、ベストウェスタン"
        ),
        "zh": (
            "您偏好什么类型的酒店？\n\n"
            "  - 豪华 -- 五星级：丽思卡尔顿、四季酒店\n"
            "  - 高级 -- 精品：万豪、希尔顿\n"
            "  - 经济 -- 舒适：假日酒店、最佳西方"
        ),
        "pt": (
            "Que tipo de hotéis você prefere?\n\n"
            "  - Luxo -- Cinco estrelas: Ritz-Carlton, Four Seasons\n"
            "  - Premium -- Alto padrão: Marriott, Hilton\n"
            "  - Econômico -- Confortável: Holiday Inn, Best Western"
        ),
        "ar": (
            "ما نوع الفنادق التي تفضلها؟\n\n"
            "  - فاخرة -- خمس نجوم: ريتز كارلتون، فور سيزونز\n"
            "  - متميزة -- راقية: ماريوت، هيلتون\n"
            "  - اقتصادية -- مريحة: هوليداي إن، بست ويسترن"
        ),
    },
    "q_rail": {
        "en": "Have you taken a rail vacation before?\n\n_e.g. first time, a few times, or very experienced._",
        "fr": "Avez-vous déjà fait des vacances en train ?\n\n_ex. première fois, quelques fois, ou très expérimenté._",
        "es": "¿Ha tomado vacaciones en tren antes?\n\n_ej. primera vez, algunas veces, o muy experimentado._",
        "de": "Haben Sie schon einmal eine Zugreise gemacht?\n\n_z.B. erstes Mal, einige Male, oder sehr erfahren._",
        "it": "Hai mai fatto una vacanza in treno?\n\n_es. prima volta, alcune volte, o molto esperto._",
        "hi": "क्या आपने पहले रेल यात्रा की है?\n\n_जैसे पहली बार, कुछ बार, या बहुत अनुभवी।_",
        "ja": "鉄道旅行の経験はありますか？\n\n_例：初めて、何度か、とても経験豊富。_",
        "zh": "您以前坐过火车旅行吗？\n\n_例如：第一次、几次、或非常有经验。_",
        "pt": "Você já fez férias de trem antes?\n\n_ex. primeira vez, algumas vezes, ou muito experiente._",
        "ar": "هل سبق لك القيام برحلة قطار؟\n\n_مثال: أول مرة، بضع مرات، أو خبير جداً._",
    },
    "q_budget": {
        "en": (
            "Last question -- do you have a budget per person, or any special requirements?\n\n"
            "_e.g. £3,000 per person, wheelchair accessible, dietary needs -- or type **no budget limit** to skip._"
        ),
        "fr": (
            "Dernière question -- avez-vous un budget par personne ou des besoins particuliers ?\n\n"
            "_ex. 3 000 € par personne, accessibilité, régime alimentaire -- ou tapez **pas de limite** pour passer._"
        ),
        "es": (
            "Última pregunta -- ¿algún presupuesto por persona o requisitos especiales?\n\n"
            "_ej. 3.000 € por persona, accesibilidad, dieta -- o escriba **sin límite** para continuar._"
        ),
        "de": (
            "Letzte Frage -- haben Sie ein Budget pro Person oder besondere Anforderungen?\n\n"
            "_z.B. 3.000 € pro Person, Barrierefreiheit, Ernährungsbedürfnisse -- oder tippen Sie **kein Limit** zum Überspringen._"
        ),
        "it": (
            "Ultima domanda -- avete un budget per persona o requisiti speciali?\n\n"
            "_es. 3.000 € a persona, accessibilità, esigenze alimentari -- o scrivete **nessun limite** per saltare._"
        ),
        "hi": (
            "आखिरी सवाल -- प्रति व्यक्ति कोई बजट या विशेष आवश्यकताएं?\n\n"
            "_जैसे ₹2,50,000 प्रति व्यक्ति, सुलभता, आहार -- या **कोई बजट सीमा नहीं** टाइप करें।_"
        ),
        "ja": (
            "最後の質問 -- お一人様あたりのご予算や特別なご要望はありますか？\n\n"
            "_例：30万円、バリアフリー、食事制限 -- または **予算制限なし** と入力してスキップ。_"
        ),
        "zh": (
            "最后一个问题 -- 每人预算范围或特殊要求？\n\n"
            "_例如：每人3万元、无障碍设施、饮食需求 -- 或输入 **无预算限制** 跳过。_"
        ),
        "pt": (
            "Última pergunta -- algum orçamento por pessoa ou requisitos especiais?\n\n"
            "_ex. R$15.000 por pessoa, acessibilidade, alimentação -- ou digite **sem limite** para pular._"
        ),
        "ar": (
            "سؤال أخير -- هل لديكم ميزانية للشخص الواحد أو متطلبات خاصة؟\n\n"
            "_مثال: 3,000 جنيه للشخص، إمكانية الوصول، احتياجات غذائية -- أو اكتب **بدون حد** للتخطي._"
        ),
    },

    # ---- Key phrases ----
    "outstanding_choice": {
        "en": "Outstanding choice",
        "fr": "Excellent choix",
        "es": "Excelente elección",
        "de": "Ausgezeichnete Wahl",
        "it": "Ottima scelta",
        "hi": "बहुत बढ़िया चुनाव",
        "ja": "素晴らしい選択",
        "zh": "出色的选择",
        "pt": "Excelente escolha",
        "ar": "اختيار رائع",
    },
    "searching_for": {
        "en": "Wonderful -- searching packages for {dest}.",
        "fr": "Magnifique -- recherche de forfaits pour {dest}.",
        "es": "Maravilloso -- buscando paquetes para {dest}.",
        "de": "Wunderbar -- ich suche Pakete für {dest}.",
        "it": "Meraviglioso -- cerco pacchetti per {dest}.",
        "hi": "शानदार -- {dest} के लिए पैकेज खोज रहा हूँ।",
        "ja": "素晴らしい -- {dest}のパッケージを検索中。",
        "zh": "太好了 -- 正在搜索{dest}的套餐。",
        "pt": "Maravilhoso -- procurando pacotes para {dest}.",
        "ar": "رائع -- أبحث عن باقات لـ {dest}.",
    },
    "here_is_search": {
        "en": "Here is what I will search for:",
        "fr": "Voici ce que je vais rechercher :",
        "es": "Esto es lo que buscaré:",
        "de": "Hier ist, wonach ich suchen werde:",
        "it": "Ecco cosa cercherò:",
        "hi": "यहाँ वह है जो मैं खोजूँगा:",
        "ja": "以下の条件で検索します：",
        "zh": "以下是我将搜索的内容：",
        "pt": "Aqui está o que vou procurar:",
        "ar": "إليك ما سأبحث عنه:",
    },
    "here_is_searched": {
        "en": "Here is what I searched for:",
        "fr": "Voici ce que j'ai recherché :",
        "es": "Esto es lo que busqué:",
        "de": "Hier ist, wonach ich gesucht habe:",
        "it": "Ecco cosa ho cercato:",
        "hi": "यहाँ वह है जो मैंने खोजा:",
        "ja": "以下の条件で検索しました：",
        "zh": "以下是我搜索的内容：",
        "pt": "Aqui está o que procurei:",
        "ar": "إليك ما بحثت عنه:",
    },
    "your_recs": {
        "en": "Your personalised recommendations:",
        "fr": "Vos recommandations personnalisées :",
        "es": "Sus recomendaciones personalizadas:",
        "de": "Ihre personalisierten Empfehlungen:",
        "it": "Le vostre raccomandazioni personalizzate:",
        "hi": "आपकी व्यक्तिगत सिफारिशें:",
        "ja": "あなたへのおすすめ：",
        "zh": "您的个性化推荐：",
        "pt": "Suas recomendações personalizadas:",
        "ar": "توصياتكم الشخصية:",
    },
    "no_matches": {
        "en": "No exact matches found. Try broadening your preferences, or speak with a Railbookers advisor for a bespoke itinerary.",
        "fr": "Aucune correspondance exacte trouvée. Essayez d'élargir vos préférences ou parlez à un conseiller Railbookers.",
        "es": "No se encontraron coincidencias exactas. Intente ampliar sus preferencias o hable con un asesor de Railbookers.",
        "de": "Keine genauen Treffer gefunden. Versuchen Sie, Ihre Präferenzen zu erweitern, oder sprechen Sie mit einem Railbookers-Berater.",
        "it": "Nessuna corrispondenza esatta. Prova ad ampliare le tue preferenze o parla con un consulente Railbookers.",
        "hi": "कोई सटीक मिलान नहीं मिला। अपनी प्राथमिकताएं बढ़ाएं या Railbookers सलाहकार से बात करें।",
        "ja": "正確な一致が見つかりませんでした。条件を広げるか、Railbookersアドバイザーにご相談ください。",
        "zh": "未找到完全匹配。请尝试扩大偏好，或联系Railbookers顾问获取定制行程。",
        "pt": "Nenhuma correspondência exata encontrada. Tente ampliar suas preferências ou fale com um consultor Railbookers.",
        "ar": "لم يتم العثور على تطابقات. حاول توسيع تفضيلاتك أو تحدث مع مستشار Railbookers.",
    },
    "does_look_right": {
        "en": "Does this look right? Click Search now to find your perfect trips, or tell me what to change.",
        "fr": "Cela vous convient-il ? Cliquez Rechercher pour trouver vos voyages parfaits, ou dites-moi ce qu'il faut modifier.",
        "es": "¿Está correcto? Haga clic en Buscar para encontrar sus viajes perfectos o dígame qué cambiar.",
        "de": "Sieht das richtig aus? Klicken Sie auf Suchen, um Ihre perfekten Reisen zu finden.",
        "it": "Ti sembra giusto? Clicca Cerca ora per trovare i tuoi viaggi perfetti o dimmi cosa cambiare.",
        "hi": "क्या यह सही लग रहा है? अभी खोजें पर क्लिक करें, या बताएं क्या बदलना है।",
        "ja": "これでよろしいですか？「今すぐ検索」をクリックするか、変更点をお知らせください。",
        "zh": "看起来对吗？点击'立即搜索'或告诉我需要更改什么。",
        "pt": "Parece correto? Clique em Pesquisar para encontrar suas viagens perfeitas ou me diga o que mudar.",
        "ar": "هل يبدو هذا صحيحاً؟ انقر على 'ابحث الآن' أو أخبرني بما يجب تغييره.",
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
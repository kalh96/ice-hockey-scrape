"""
Name lists for fictional player and team generation.
Broad international mix reflecting the global reach of professional hockey.
"""

FIRST_NAMES = [
    # Scottish / British
    "Liam", "Callum", "Ewan", "Fraser", "Hamish", "Iain", "Jamie", "Kyle",
    "Logan", "Murray", "Neil", "Robbie", "Scott", "Stuart", "Angus",
    "Connor", "Dylan", "Finn", "Glen", "Ross", "Rory", "Gregor", "Craig",
    "Ryan", "Kieran", "Blair", "Graeme", "Duncan", "Marcus", "Derek",
    "Alistair", "Alec", "Euan", "Grant", "Lewis", "Malcolm", "Niall",
    "Ruaridh", "Struan", "Tam", "Archie", "Brodie", "Caleb", "Declan",
    # Canadian / North American
    "Tyler", "Brandon", "Jordan", "Justin", "Nathan", "Travis", "Brett",
    "Cody", "Tanner", "Riley", "Brady", "Cole", "Hunter", "Dillon",
    "Garrett", "Shane", "Zach", "Blake", "Chase", "Bryce", "Reid",
    "Colton", "Jared", "Kaden", "Lance", "Troy", "Wade", "Cade",
    # Nordic / Scandinavian
    "Erik", "Lars", "Mikael", "Henrik", "Johan", "Niklas", "Patrik",
    "Sven", "Anders", "Bjorn", "Mattias", "Emil", "Anton", "Viktor",
    "Oskar", "Tobias", "Gustav", "Axel", "Felix", "Simon", "Lukas",
    # Eastern European
    "Pavel", "Dmitri", "Alexei", "Sergei", "Ivan", "Mikhail", "Andrei",
    "Jakub", "Tomas", "Martin", "Marek", "Radek", "Petr", "Ondrej",
    # East Asian — Japanese / Korean / Chinese
    "Yuto", "Kenji", "Haruki", "Takashi", "Ryo", "Daiki", "Shota",
    "Jae-won", "Min-jun", "Sung-ho", "Hyun", "Joon", "Seung",
    "Wei", "Jian", "Hao", "Ming", "Tao", "Lei", "Fang",
    # South / Southeast Asian
    "Arjun", "Rohan", "Vikram", "Kiran", "Sahil", "Rajan", "Priya",
    "Rafi", "Dani", "Budi", "Hendra", "Rizal",
    # African — West African / East African / Southern African
    "Kofi", "Kwame", "Ade", "Emeka", "Chidi", "Tunde", "Segun",
    "Amara", "Moussa", "Ibrahim", "Oumar", "Seydou", "Mamadou",
    "Tendai", "Sipho", "Thabo", "Lebo", "Siya", "Lungelo", "Amos",
    "Kelvin", "Festus", "Chukwu", "Nnamdi", "Obinna",
    # South American — Brazilian / Argentine / Chilean
    "Mateus", "Gabriel", "Rafael", "Lucas", "Felipe", "Bruno", "Thiago",
    "Gustavo", "Diego", "Rodrigo", "Leonardo", "Vinicius", "Caio",
    "Nicolás", "Facundo", "Matías", "Ezequiel", "Tomás", "Agustín",
    "Sebastián", "Joaquín", "Ignacio", "Maximiliano",
    "Alejandro", "Carlos", "Eduardo", "Francisco", "Andrés",
]

LAST_NAMES = [
    # Scottish
    "MacDonald", "Campbell", "Morrison", "MacLeod", "Stewart", "Reid",
    "Murray", "Fraser", "Robertson", "MacKenzie", "Davidson", "Gibson",
    "Hamilton", "Hunter", "Mackay", "Sinclair", "Wallace", "Anderson",
    "Burns", "Crawford", "Douglas", "Fleming", "Gordon", "Henderson",
    "Johnston", "Kennedy", "Lindsay", "Martin", "Nicholson", "Patterson",
    "Quinn", "Russell", "Sutherland", "Thomson", "Williamson", "Young",
    "MacPherson", "MacGregor", "MacMillan", "MacIntyre", "MacLean",
    # British / English
    "Smith", "Wilson", "Taylor", "Brown", "Johnson", "Williams", "Jones",
    "Miller", "Davis", "Moore", "White", "Harris", "Clark", "Lewis",
    "Walker", "Hall", "Allen", "Wright", "Scott", "Green", "Baker",
    "Adams", "Nelson", "Carter", "Mitchell", "Turner", "Parker", "Evans",
    # Nordic
    "Larsson", "Johansson", "Eriksson", "Nilsson", "Lindqvist", "Bergstrom",
    "Andersen", "Nielsen", "Petersen", "Hansen", "Svensson", "Karlsson",
    "Magnusson", "Lindberg", "Gustafsson", "Holm", "Lund", "Berg",
    # Eastern European
    "Kozlov", "Sokolov", "Volkov", "Lebedev", "Popov", "Morozov",
    "Novak", "Horak", "Dvorak", "Krejci", "Chara", "Plekanec", "Hudacek",
    # East Asian
    "Tanaka", "Yamamoto", "Sato", "Suzuki", "Watanabe", "Ito", "Nakamura",
    "Kobayashi", "Kato", "Yoshida", "Hayashi", "Kimura", "Matsumoto",
    "Kim", "Lee", "Park", "Choi", "Jung", "Yoon", "Lim", "Han",
    "Chen", "Wang", "Li", "Zhang", "Liu", "Yang", "Wu", "Zhou",
    # South / Southeast Asian
    "Sharma", "Patel", "Singh", "Kumar", "Gupta", "Mehta", "Nair",
    "Santoso", "Wijaya", "Pratama", "Putra", "Kusuma",
    # African
    "Okafor", "Mensah", "Diallo", "Toure", "Coulibaly", "Keita", "Traore",
    "Osei", "Asante", "Boateng", "Owusu", "Agyemang",
    "Dlamini", "Ndlovu", "Mokoena", "Khumalo", "Nkosi", "Sithole",
    "Okonkwo", "Adeyemi", "Nwosu", "Eze", "Onuoha", "Ihejirika",
    # South American
    "Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira",
    "Alves", "Nascimento", "Lima", "Carvalho", "Araujo", "Barbosa",
    "González", "Rodríguez", "Martínez", "López", "García", "Fernández",
    "Pérez", "Sánchez", "Ramírez", "Torres", "Flores", "Morales",
    "Vargas", "Reyes", "Cruz", "Herrera", "Medina", "Rojas",
]

# Team nickname pool — used when generating fictional teams
NICKNAMES = [
    "Tigers", "Wolves", "Eagles", "Bears", "Lions", "Falcons",
    "Ravens", "Hawks", "Stags", "Foxes", "Vipers", "Cobras",
    "Thunder", "Storm", "Blizzard", "Frost", "Freeze", "Avalanche",
    "Knights", "Warriors", "Raiders", "Hunters", "Blazers", "Flames",
    "Predators", "Sabres", "Blades", "Lancers", "Monarchs", "Sentinels",
    "Phantoms", "Reapers", "Titans", "Spartans", "Gladiators",
]

# City pool — used when generating fictional teams
CITIES = [
    "Glasgow", "Edinburgh", "Dundee", "Aberdeen", "Inverness", "Perth",
    "Stirling", "Falkirk", "Hamilton", "Ayr", "Kilmarnock", "Paisley",
    "Motherwell", "Greenock", "Dumfries", "Elgin", "Fort William",
    "St Andrews", "Kirkcaldy", "Livingston", "Bathgate", "Cumbernauld",
]

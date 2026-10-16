# initialization of choices for production models

SHOOTING_FORMAT_CHOICES = (
    ("SUP8", "Super 8"),
    ("SUP16", "Super 16"),
    ("SUP35", "Super 35"),
    ("35MM", "35 MM"),
    ("70MM", "70 MM"),
    ("DV", "DV"),
    ("DVCAM", "DVCAM"),
    ("HD", "HD (Standard)"),
    ("HDCAM", "HDCAM"),
    ("HDCINE", "HD CINEMASCOPE"),
    ("CREANUM", "Création Numérique (Générique)"),
    ("BETASP", "BETA SP"),
    ("BETANUM", "BETA Numérique"),
    ("DIGICAM", "Appareil Photo Numérique"),
    ("MOBILE", "Mobile"),
    ("HI8", "HI8"),
    ("AVCHD", "AVCHD"),
    ("XDCAMEX", "XDCAM EX"),
    ("3DREL", "Relief 3D"),
    ("2K", "2K"),
    ("4K", "4K"),
    ("6K", "6K"),
    ("8K", "8K"),
    ("ARRICAM", "ARRI CAM (Numérique)"),
    ("RED", "RED (Numérique)"),
    ("SONYCINE", "SONY Cinéma (Numérique)"),
    ("BLACKMAGIC", "Blackmagic (Numérique)"),
)

ASPECT_RATIO_CHOICES = (
    ("1.33", "1.33 (4/3)"),
    ("1.37", "1.37 (Académie)"),
    ("1.50", "1.50 (3:2 / VistaVision)"),
    ("1.66", "1.66 (Widescreen Européen)"),
    ("1.77", "1.77 (16/9)"),
    ("1.85", "1.85 (Flat)"),
    ("1.89", "1.89 (DCI Native Aspect Ratio)"),
    ("1.90", "1.90 (IMAX Numérique / DCI Full Container)"),
    ("2.00", "2.00 (Univisium)"),
    ("2.20", "2.20 (70mm)"),
    ("2.39", "2.39 (Scope)"),
    ("2.76", "2.76 (Ultra Panavision 70)"),
)

PROCESS_CHOICES = (
    ("COLOR", "Couleur"),
    ("BW", "Noir & Blanc"),
    ("COLORBW", "Noir & Blanc & Couleur"),
    ("SEPIA", "Sépia"),
    ("COLORIZE", "Colorisation"),
    ("MONOCHROME", "Monochrome (Teinte Spécifique)"),
    ("VINTAGE", "Vintage / Vieilli"),
    ("HDR", "HDR (High Dynamic Range)"),
    ("LOG", "Log (Courbe Logarithmique)"),
    ("RAW", "RAW (Brut)"),
)

AUDIO_FEATURE_CHOICES = (
    ("SILENT", "Muet"),
    ("SOUND", "Sonore"),
    ("DIALOGUES", "Dialogues"),
    ("VOICEOVER", "Voix off"),
    ("INTERTITLES", "Intertitres"),
)

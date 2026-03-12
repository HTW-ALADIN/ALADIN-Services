from enum import Enum


class ModelKeys(str, Enum):
    mumax = "mumax"
    KS1 = ("KS1",)
    KS2 = ("KS2",)
    KMS1 = ("KMS1",)
    YXS1 = ("YXS1",)
    YXS2 = ("YXS2",)
    YXO2 = ("YXO2",)
    KS_O2 = ("KS_O2",)
    prod = ("Prod",)
    alpha = ("alpha",)
    beta = ("beta",)
    YPS1 = ("YPS1",)
    RQ_x = ("RQ_x",)
    Y_CO2_P = ("Y_CO2_P",)
    pH_min = "pH_min"
    pH_opt = "pH_opt"
    pH_max = "pH_max"
    T_min = "T_min"
    T_opt = "T_opt"
    T_max = "T_max"
    substrate_1 = ("Substrat 1",)
    substrate_2 = ("Substrat 2",)
    product = ("Produkt",)
    microorganism = ("Mikroorganismus",)
    description = "Beschreibung"

from enum import Enum


class ResultKeys(str, Enum):
    t = ("t",)
    c_x = ("c_x",)
    c_S1 = ("c_S1",)
    c_S2 = ("c_S2",)
    c_P = ("c_P",)
    c_DO = ("c_DO",)
    c_O2_Out = ("c_O2_Out",)
    c_CO2_Out = ("c_CO2_Out",)
    sum_Feed = ("Sum_Feed",)
    fumigation_rate = ("Begasungsrate",)
    rotation_rate = ("Drehzahl",)
    pressure = ("Druck",)
    our = ("OUR",)
    cer = ("CER",)
    rq = ("RQ",)
    c_DO_prozs = ("c_DO_proz",)
    v_l = ("V_L",)

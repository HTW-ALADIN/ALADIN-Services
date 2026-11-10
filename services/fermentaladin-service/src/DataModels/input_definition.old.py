from enum import Enum


class InputKeys(str, Enum):
    model = ("Model",)
    phase = ("Phase",)
    q_air = ("Q_Air",)
    bolus_c = ("Bolus_C",)
    feed_c = ("Feed_C",)
    bolus_n = ("Bolus_N",)
    feed_n = ("Feed_N",)
    rpm = ("Drehzahl",)
    pressure = ("Druck",)
    duration = ("Dauer",)
    start_vol = ("V_L",)
    temp = ("T",)
    ph = ("pH",)
    do = ("DO",)
    density = ("Dichte",)
    c_x0 = ("c_x0",)
    q_in = ("Q_in",)
    q_out = ("Q_Out",)
    c_o2_sat = "c_O2_sat"

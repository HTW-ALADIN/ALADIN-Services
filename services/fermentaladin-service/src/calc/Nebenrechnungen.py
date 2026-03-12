import logging


def Nebenrechnungen(Mpars_in, df_Fpar_in):
    # Mpars is of datatype series
    # df_Fpar_in is of datatype dataframe
    import math

    import numpy as np

    #############################################################
    # Nebenrechnungen
    #############################################################

    Mpars_out = Mpars_in
    df_Fpar_out = df_Fpar_in
    logging.debug(f" Nebenrechnung: {Mpars_in}")
    #############################################################
    # Sicherstellen das folgende Werte nicht exakt Null sind
    #############################################################
    # Mpars_out["YPS1"]=Mpars_out["YPS1"].astype(float) #just to make sure it is really float
    # Mpars_out["Y_CO2_P"]=Mpars_out["Y_CO2_P"].astype(float)
    # produces a warning...and mybe is not needed for a series

    if Mpars_in["YPS1"] == 0:
        Mpars_out["YPS1"] = 1 * 10 ** (
            -25
        )  # avoid division by Zero in calc of mu_s by setting Yps to a very small number

    if Mpars_in["Y_CO2_P"] == 0:
        Mpars_out["Y_CO2_P"] = 1 * 10 ** (-25)
        # avoid division by Zero by setting parameter to a very small number

    ##globale Variablen zuweisen
    V_L_0 = df_Fpar_in["V_L"][0]  # Startvolumen in L TODO- erötern: maximales Arbeitsvolumen oder Startvolumen
    #############################################################
    # Berechnung der Sauerstofflöslichkeit zu Beginn jeder Phase
    #############################################################
    MW_O2 = 32  # Molmasse Sauerstoff O2 in g/mol
    kH_pc_Std = 779.4  # Henry Flüchtigkeitskonstante bei 25°C für O2 in L *bar *mol-1
    T_Std = 25 + 273.15  # Standardtemperatur in K;
    T = df_Fpar_in.at[0, "T"] + 273.15  # Fermentationstemperatur in K;
    kH_pc_T = kH_pc_Std * math.exp(-1700 * (1.0 / T - 1 / T_Std))
    c_O2_sat = df_Fpar_in["Druck"] + 1.013  # Druck in bara
    c_O2_sat = c_O2_sat * 0.20946 / kH_pc_T * MW_O2  # Löslichkeit O2 in g/L
    df_Fpar_out["c_O2_sat"] = c_O2_sat
    #############################################################

    #############################################################
    # Umrechnung des eingestellten Zuluftstroms von NL/min in m³/s
    #############################################################
    Q_Air_sec = (df_Fpar_in["Q_Air"] / 60) * 1 / 1000
    #############################################################

    #############################################################
    # Berechnungen des kLa-Wertes für jede Phase
    # Reaktorgeomeotrie: Tankvolumen = 0,1 m³
    #############################################################

    # Berechnung der Tank cross-sectional area
    V_T = 0.1  # m³ - Totalvolumen des Tanks
    d_T = (V_T / 3 * 4 / math.pi) ** (1 / 3)  # Tank diameter in m
    d_I = d_T * 1 / 3  # Diameter Impeller at a given d_T/d_I of 1/3
    A_T = math.pi / 4 * d_T**2  # calc cross sectional area of tank in m²

    # Berechung der Leerrohrgeschwindigkeit
    v_g = Q_Air_sec / A_T  # vg in m/sec
    logging.debug(f" v_g: {v_g}")
    # Berechnung des kla Wertes für jede Phase
    Ne = 5
    # Newton Zahl für Rushton Impeller bei turbulenter Strömung nach Bates, 1963
    K_A = 490  # constant for calc. P gassed fpr 2 Impellers
    g = 9.81  # m/s^2 Fallbeschleunigung
    n_impellers = 2
    Dichte = 1050  # kg/m³ assumption for fermentation broth density
    P = (
        Ne * n_impellers * Dichte * (df_Fpar_in["Drehzahl"].values / 60) ** 3 * d_I**5
    )  # calculation Power input ungassed by Phase in Watt
    d = 1 + (K_A * v_g) / math.sqrt(g * d_I)
    Pg = P / np.sqrt(d)
    V_L_m3 = V_L_0 / 1000  # Medienvolumen in m³
    kLa = 0.026 * (Pg / V_L_m3) ** 0.4 * v_g**0.5 * 3600  # calc kLa in 1/h
    df_Fpar_out["kLa"] = kLa
    logging.debug(f"kLa: {df_Fpar_out['kLa']}")

    return [Mpars_out, df_Fpar_out]

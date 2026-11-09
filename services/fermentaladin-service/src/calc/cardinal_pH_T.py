# calculates µ_max at a given model, pH and Temperature (T)
# Berechnung der spezifischen Wachstumsrate nach dem Kardinalmodell


def cardinal_pH_T(Mpars, pH, T) -> float:

    mu_max_opt = Mpars["mumax"]
    pH_min = Mpars["pH_min"]
    pH_opt = Mpars["pH_opt"]
    pH_max = Mpars["pH_max"]
    T_min = Mpars["T_min"]
    T_opt = Mpars["T_opt"]
    T_max = Mpars["T_max"]

    # Temperatur- und pH-Abhängigkeit

    if (pH <= pH_min) or (pH >= pH_max):
        gamma_pH = 0
    else:
        gamma_pH = ((pH - pH_min) * (pH - pH_max)) / ((pH - pH_min) * (pH - pH_max) - ((pH - pH_opt) ** 2))

    if (T <= T_min) or (T >= T_max):
        gamma_T = 0
    else:
        gamma_T = ((T - T_max) * (T - T_min) ** 2) / (
            (T_opt - T_min) * ((T_opt - T_min) * (T - T_opt) - (T_opt - T_max) * (T_opt + T_min - 2 * T))
        )

    # Kombinierte Wachstumsrate
    mu_Kardinal = mu_max_opt * gamma_T * gamma_pH

    return mu_Kardinal

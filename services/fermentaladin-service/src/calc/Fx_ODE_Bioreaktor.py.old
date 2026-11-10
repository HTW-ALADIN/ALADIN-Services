def Bioreaktor_ODE(x, y, Mpar, Fpar):  # Hier werden die ODEs definiert
    # Erklärung der Variablen
    # c_O2_sat=Fpar["c_O2_sat"]          #Sauerstofflöslichkeit im Medium g/L
    # kLa=Fpar["kLa"]            #%kla Wert in 1/h Info eine OTR von 100 mmol/(L*h) entspricht bei DO=0% ~ einem kla von 400 1/h
    #   RQ_x=Mpar.RQ_x;                    #%Respiratory Coefficient for Biomass formatio
    #   Q_Air_vvm=FparS.Q_Air_vvm(phase);  #%Begasungsrate in NL(Luft)/(L(Kulturbrühe)*min) quasi vvm
    #   KS_O2=Mpar.KS_O2;                  #%Halbsaettigungskonstante Sauerstoff in g/L
    #   YXO2=Mpar.YXO2;                    #%Ausbeutekoeffizient g Biomasse je g Sauerstoff nach HArvard Bionumbers für E.coli
    #   Prod=Mpar.Prod;                    #%Produktbildung an =1 oder aus =0
    #   alpha=Mpar.alpha;                  #%Luedking Piret Parameter für wachsumassoziierte Produktbildung
    #   beta=Mpar.beta;                    #%Luedking Piret Parameter für nicht wachsumassoziierte Produktbildung
    #   KMS1=Mpar.KMS1;                    #%Km Wert in Analogie zur Michaelis Menten-Gleichung für die Bildung von P aus S - nicht wachstumsassoziiert
    #   mumax=Mpar.mumax;                  #% maximale Wachstumsrate  in 1/h
    #   KS1=Mpar.KS1;                      #% Halbsaettigungskonstante Substrat in g/L für Berechnung von Wachstumsrat µ
    #   YXS1=Mpar.YXS1;                    #% Ausbeutekoeff fuer Zellmasse in g/g
    #   KS2= Mpar.KS2;                     #%Halbsaettigungskonstante Ks für Substrat S2 in g/L für Berechnung von Wachstumsrat µ
    #   YXS2=Mpar.YXS2;                    #%Ausbeutekoeff fuer Zellmasse auf Substrat 2 1 in g/g
    #   Feed_C=FparS.Feed_C(phase);        #%Feedrate Substrat 1 in g/L*h
    #   Y_CO2_P=Mpar.Y_CO2_P;              #%Ausbeutekoeffizient CO2 aus Produktbildung je g Produkt
    #   YPS1=Mpar.YPS1;                    #%Ausbeutekoeffizient Produkt aus Substrat 1 je g Produkt

    # Zuweisungen der Eingangswerte / = Konzentrationen die das Model berechnet
    c_x = y[0]  # % Konzentration Biotrockenmasse in g/L
    c_S1 = y[1]  # % Substratkonzentration 1 in g/L
    c_S2 = y[2]  # % Substratkonzentration 2 in g/L
    c_P = y[3]  # % Produktkonzentration in g/L  # noqa: F841
    c_DO = y[4]  # % Gelöstsaurestoffkonzentration in g/L
    c_O2_Out = y[5]  # % Abluftkonzentration O2
    c_CO2_Out = y[6]  # % Abluftkonzentration CO2

    # Nebenrechnungen und Zuweisungen von Konstanten
    c_O2_Luft = 0.2095  # Sauerstoffgehalt Luft in mol(O2)/mol(Luft)
    c_CO2_Luft = 0.0004147  # CO2 Gehalt der Luft in mol(CO2)/mol(Luft)
    Vm_norm = 22.41396954  # molares Volumen bei Normbedingungen (0°C und 101,325 kPa) in L/mol
    Luft_In = Fpar["Q_Air"] * 60 / Fpar["V_L"]  # ZuLuftstrom in NL/(L_Brühe*h) mit Q_Air in NL/min

    # Berechnung der nicht differentiellen Gleichungen

    # spez. Wachstumsrate in Abhängigkeit von 3 limitierenden Substraten
    # Monod Kinetik fuer spezifische Wachstumsrate Varinate "Min-Verknüpfung"
    mu_Faktor = min(
        [
            c_S1 / (Mpar["KS1"] + c_S1),
            c_S2 / (Mpar["KS2"] + c_S2),
            c_DO / (Mpar["KS_O2"] + c_DO),
        ]
    )
    # mu_Faktor = Mpar["mumax"]*c_S1/(Mpar["KS1"]+c_S1)*c_S2/(Mpar["KS2"]+c_S2)*c_DO/(Mpar["KS_O2"]+c_DO)
    mu = Mpar["mumax"] * mu_Faktor  # spez. Wachstumsrate in 1/h
    # mu_s = mumax*cs1/(KS1+cs1)*cs2/(KS2+cs2)*c_ox/(KS_O2+c_ox); % Monod Kinetik fuer spezifische Wachstumsrate Varinate "Produkt-Verknüpfung"

    # Produktbildungsrate
    # b = beta*cs1/(KMS1+cs1)*(1-(mu_s/mumax))^200; %Michaelis Menten Kinetik für nicht wachstumssassoziierte Produktbildung
    # Alternative Code (same speed)
    if (
        mu > 1 * 10 ** (-3)
    ):  # wenn mu größer ~0 dann keine nicht wachstumsassoziierte Produktbildung; bei numerischer Integration wird mu nie exakt 0
        beta = 0
    else:
        beta = Mpar["beta"] * c_S1 / (Mpar["KMS1"] + c_S1)

    qp = Mpar["Prod"] * (mu * Mpar["alpha"] + beta)  # Luedking Piret
    OUR = c_x * (mu / Mpar["YXO2"] + 0.001)  # in g/(L*h) die 0.001 ist ein Platzhalter für den Erhaltungsstoffwechsel
    OUR = OUR / 32  # Umrechung in mol/(L*h)
    # Begasung / Sauerstoff
    CER = OUR * Mpar["RQ_x"] + c_x * (qp / Mpar["Y_CO2_P"]) / 44  # Divison durch 44: Umrechung von g/L in mol/L
    Luft_Out = Luft_In + c_x * (qp / Mpar["Y_CO2_P"]) / 44 * Vm_norm  # Volumen der Abluft ist um entstandenes CO2 höher

    #   Biomassebildung
    cx_r = mu * c_x

    # Substratverbrauchsgeschwindigkeit Substrat 1 durch Biomassebildung und Produktbildung
    c_S1_r = c_x * (-mu / Mpar["YXS1"] - qp / Mpar["YPS1"]) + Fpar["Feed_C"]

    # Substratverbrauchsgeschwindigkeit Substrat 2 durch Biomassebildung NICHT Genutzt zur Produktbildung Produktbildung
    c_S2_r = c_x * (-mu / Mpar["YXS2"])

    # Produktbildung nach Luedeking Piret;
    c_P_r = qp * c_x

    # Berechnung Gelöstsauerstoffkonzentration (OTR-OUR)
    c_DO_r = Fpar["kLa"] * (Fpar["c_O2_sat"] - c_DO) - c_x * (mu / Mpar["YXO2"])

    # Berechnung O2-gehalt in Vol% Abluft IN Analogie zu einem CSTR F(C_in-Cout)-Reaktion
    c_O2_Out_r = Luft_In * c_O2_Luft - Luft_Out * c_O2_Out - OUR * Vm_norm

    # Berechnung CO2-gehalt in Vol% Abluft IN Analogie zu einem CSTR F(C_in-Cout)-Reaktion
    c_CO2_Out_r = Luft_In * c_CO2_Luft - Luft_Out * c_CO2_Out + CER * Vm_norm

    return [cx_r, c_S1_r, c_S2_r, c_P_r, c_DO_r, c_O2_Out_r, c_CO2_Out_r]


# Information on the code
# %Set of ODEs to describe a Bioreactor based on the Monod-kinetics
# % Loesung fuer Batch - Monod
# % Features:
# %   * Drei limitierende Substrate - eines davon Sauerstoff
# %
# %    S1 - Kohlenstoffquelle
# %    S2 - Stickstoff oder Phosphor oder limitierender Nährstoff bei S1 Überschuss
# %    S3 - Sauerstoff
# %   * Bildung eines Produktes auf Basis des Substrats 1
# %   * Erhaltungsstoffwechsel - einfach ohne Konsum der Biomasse
# %   * aerober Prozess

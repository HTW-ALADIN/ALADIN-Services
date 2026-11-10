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
    #   KiP                                #Produkthemmung auf Produktbildung, Wachstumsrate
    #   KiS1                               #Substrathemmung auf Produktbildung, Wachstumsrate

    # Zuweisungen der Eingangswerte / = Konzentrationen die das Model berechnet
    # max (y,0) ist nötig um die Größen nicht kleiner 0 werden zu lassen, da dies praktisch unmöglich ist

    c_x = max(y[0], 0)  # % Konzentration Biotrockenmasse in g/L
    c_S1 = max(y[1], 0)  # % Substratkonzentration 1 in g/L
    c_S2 = max(y[2], 0)  # % Substratkonzentration 2 in g/L
    c_P = max(y[3], 0)  # % Produktkonzentration in g/L
    c_DO = max(y[4], 0)  # % Gelöstsaurestoffkonzentration in g/L; min Bedingung um negative Werte zu verhindern
    c_O2_Out = max(y[5], 0)  # % Abluftkonzentration O2 in mol/mol
    c_CO2_Out = max(y[6], 0)  # % Abluftkonzentration CO2 in mol/mol
    V_L = max(y[7], 0)

    # Volumenänderung
    Q_In = Fpar["Feed_C"] + Fpar["Feed_N"]  # flow of media into the reactor in L/h
    D = Q_In / V_L  # Definition of the dilution rate

    # Berechnung der nicht differentiellen Gleichungen

    # spez. Wachstumsrate in Abhängigkeit von 3 limitierenden Substraten
    # Monod Kinetik fuer spezifische Wachstumsrate Varinate "Min-Verknüpfung"
    mu_Faktor = min(
        [
            c_S1 / (Mpar["KS1"] + c_S1 * (1 + c_S1 / Mpar["KiS1"])),
            c_S2 / (Mpar["KS2"] + c_S2),
            c_DO / (Mpar["KS_O2"] + c_DO),
        ]
    )
    # mu_Faktor = Mpar["mumax"]*c_S1/(Mpar["KS1"]+c_S1)*c_S2/(Mpar["KS2"]+c_S2)*c_DO/(Mpar["KS_O2"]+c_DO)
    mu = Mpar["mumax"] * mu_Faktor  # spez. Wachstumsrate in 1/h
    # mu_s = mumax*cs1/(KS1+cs1)*cs2/(KS2+cs2)*c_ox/(KS_O2+c_ox); % Monod Kinetik fuer spezifische Wachstumsrate Varinate "Produkt-Verknüpfung"

    # Produktbildungsrate

    # b = beta*cs1/(KMS1+cs1)*(1-(mu_s/mumax))**200; %Michaelis Menten Kinetik für nicht wachstumssassoziierte Produktbildung
    # Alternative Code (same speed)
    if (
        mu > 1 * 10 ** (-3)
    ):  # wenn mu größer ~0 dann keine nicht wachstumsassoziierte Produktbildung; bei numerischer Integration wird mu nie exakt 0
        beta = 0
        alpha = Mpar["alpha"] * c_S1 / (Mpar["KMS1"] + c_S1)
    else:
        beta = Mpar["beta"] * c_S1 / (Mpar["KMS1"] + c_S1 * (1 + c_S1 / Mpar["KiS1"]))
        alpha = 0

    if Q_In > 0:
        c_S1_Feed = (
            Fpar["c_C_Source"] * Fpar["Feed_C"] * 1 / Q_In
        )  # since 2 substrates are fed we need to calc the c_ substrate in the combined feed
        c_S2_Feed = (
            Fpar["c_N_Source"] * Fpar["Feed_N"] * 1 / Q_In
        )  # since 2 substrates are fed we need to calc the c_ substrate in the combined feed

    else:
        c_S1_Feed = 0
        c_S2_Feed = 0

    qp = Mpar["Prod"] * (mu * alpha + beta)  # Luedking Piret product formation
    q_S1 = -mu / Mpar["YXS1"] - qp / Mpar["YPS1"]
    q_S2 = -mu / Mpar["YXS2"]

    # Begasung / Sauerstoff
    kla = Fpar["kLa"]
    dO2 = Fpar["c_O2_sat"] - c_DO
    OTR = kla * dO2  # in g/(L*h)

    # nette Idee, aber inkludiert nicht den Fakt, dass man die Begasung auch mal abstellt..also verwerfen
    # OTR_max=kla*Fpar["c_O2_sat"]
    # OUR=min(c_x*mu/Mpar["YXO2"]+0.001, OTR_max) #OUR kann nicht höher als die max OTR sein in g/(L*h) die 0.001 ist ein Platzhalter für den Erhaltungsstoffwechsel

    OUR = c_x * mu / Mpar["YXO2"] + 0.001
    # print(f"mu={mu} and OUR={OUR/32*1000} and OTR_max={OTR_max}")
    OUR_mol = OUR / 32  # Umrechung in mol/(L*h)

    CER_mol = OUR_mol * Mpar["RQ_x"] + c_x * (qp / Mpar["Y_CO2_P"]) / 44  # Divison durch 44: Umrechung von g/L in mol/L
    # if OUR>OTR_max: print("impossible")
    # Biomassebildung
    cx_r = (mu - D) * c_x

    # Substratverbrauchsgeschwindigkeit Substrat 1 durch Biomassebildung und Produktbildung

    c_S1_r = D * (c_S1_Feed - c_S1) + q_S1 * c_x

    # Substratverbrauchsgeschwindigkeit Substrat 2 durch Biomassebildung NICHT Genutzt zur Produktbildung Produktbildung

    c_S2_r = D * (c_S2_Feed - c_S2) + q_S2 * c_x

    # Produktbildung nach Luedeking Piret;
    c_P_r = qp * c_x - D * c_P

    # Berechnung Gelöstsauerstoffkonzentration (OTR-OUR)
    c_DO_r = OTR - OUR

    # Berechnung der Gasbilanzen

    # Nebenrechnungen und Zuweisungen von Konstanten
    c_O2_Luft = 0.2095  # Sauerstoffgehalt Luft in mol(O2)/mol(Luft)
    c_CO2_Luft = 0.0004147  # CO2 Gehalt der Luft in mol(CO2)/mol(Luft)
    Vm_norm = 22.41396954  # molares Volumen bei Normbedingungen (0°C und 101,325 kPa) in L/mol
    Q_gas = Fpar["Q_Air"] * 60  # Molenstrom gesamt in mol/h mit Q_Air in NL/min - Einheit finel: mol/h;
    V_gas_phase = 150 - V_L

    # Berechnung O2-gehalt in mole fraction Abluft IN Analogie zu einem CSTR dc/dt=F(C_in-Cout)-Reaktion
    # Division durchs HEadspacevolumen ergibt die Verdünnungsrate für das Headspace Gas
    c_O2_Out_r = Q_gas / V_gas_phase * (c_O2_Luft - c_O2_Out) - OUR_mol * V_L / V_gas_phase * Vm_norm

    c_CO2_Out_r = Q_gas / V_gas_phase * (c_CO2_Luft - c_CO2_Out) + CER_mol * V_L / V_gas_phase * Vm_norm

    # Berechnung des Volumens

    v_L_r = Q_In - Fpar["Q_out"]

    return [cx_r, c_S1_r, c_S2_r, c_P_r, c_DO_r, c_O2_Out_r, c_CO2_Out_r, v_L_r]


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

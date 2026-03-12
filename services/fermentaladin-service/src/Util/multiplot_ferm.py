def multiplot_ferm(results_df):
    import matplotlib.pyplot as plt
    import numpy as np

    # PLOTTING
    schwarz = (0, 0, 0)
    turkis = (102 / 255, 194 / 255, 165 / 255)
    orange = (249 / 255, 155 / 255, 25 / 255)  # HTW Orange
    blau = (141 / 255, 160 / 255, 203 / 255)
    violet = (231 / 255, 138 / 255, 195 / 255)
    gruen = (166 / 255, 216 / 255, 84 / 255)
    gelb = (255 / 255, 217 / 255, 47 / 255)
    rot = (163 / 255, 106 / 255, 105 / 255)
    hellgrau = (179 / 255, 179 / 255, 179 / 255)  # noqa: F841

    labelsize = 12  # setting the fontsize of the axis labels

    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2)

    ax1.plot(results_df["t"], results_df["Sum_Feed"], label="sum_feeding", color=gelb)
    ax1.plot(results_df["t"], results_df["c_S1"], label="$c_{S1}$", color=orange)
    ax1.set_ylabel("$c_{S1} [g/L], m_{Feed S1} [g]$", fontsize=labelsize)
    ax1.grid()
    ax1.set_ylim(bottom=0)
    ax1.set_title("Substrate", fontsize=labelsize + 3)

    ax12 = ax1.twinx()
    ax1.plot(np.nan, color=blau, label="$c_{S2}$")  # only to get an entry in ax1 legend
    ax12.plot(results_df["t"], results_df["c_S2"], color=blau)
    ax12.set_ylim(bottom=0)
    ax12.set_ylabel("$c_{S2} [g/L]$", fontsize=labelsize)
    ax12.yaxis.label.set_color(blau)
    ax12.tick_params(axis="y", labelcolor=blau)
    ax12.spines["right"].set_color(blau)
    # ax12.spines[["right","left","bottom"]].set_linewidth(2)
    ax1.legend()

    ax2.plot(results_df["t"], results_df["Druck"], label="Druck", color=turkis)
    ax2.plot(results_df["t"], results_df["Begasungsrate"], label="Begasungsrate", color=blau)
    ax2.set_ylabel(r"$p [barg], Q_{O2} [NL \cdot L^{-1} \cdot min^{-1}]$", fontsize=labelsize)
    ax2.grid()
    ax2.set_ylim(bottom=0)

    ax22 = ax2.twinx()
    ax2.plot(np.nan, color=schwarz, linestyle="--", label="Drehzahl")  # only to get an entry in ax2 legend
    ax2.plot(np.nan, color=gruen, label="DO")  # only to get an entry in ax2 legend

    ax22.plot(results_df["t"], results_df["Drehzahl"] / 10, linestyle="--", color=schwarz)
    ax22.plot(results_df["t"], results_df["c_DO_proz"], label="DO", color=gruen)
    ax22.set_ylabel("n [rpm/10], DO [%]", fontsize=labelsize)
    ax22.set_ylim(bottom=0)
    ax2.legend()
    ax2.set_title("Sauerstoffversorgung", fontsize=labelsize + 3)

    ax3.plot(results_df["t"], results_df["c_x"], label="c_x", color=violet)
    ax3.plot(results_df["t"], results_df["c_P"], label="c_P", color=rot)
    ax3.set_ylabel("$c_{x} [g/L], c_{P} [g/L]$", fontsize=labelsize)
    ax3.grid()
    ax3.set_ylim(bottom=0)

    ax32 = ax3.twinx()
    ax3.plot(np.nan, color=schwarz, linestyle="--", label="Volumen")  # only to get an entry in ax3 legend

    ax32.plot(results_df["t"], results_df["V_L"], linestyle="--", color=schwarz)
    ax32.set_ylabel("Volumen in L", fontsize=labelsize)
    ax32.set_ylim(bottom=0)

    ax3.legend(loc="lower right")
    ax3.set_title("Produkte", fontsize=labelsize + 3)

    ax4.plot(results_df["t"], results_df["OUR"], label="OUR", color=rot)
    ax4.set_ylabel(r"$OUR [mmol \cdot L^{-1} \cdot h^{-1}]$", fontsize=labelsize)
    ax4.grid()
    ax4.set_ylim(bottom=0)

    ax42 = ax4.twinx()
    ax4.plot(np.nan, color=schwarz, label="RQ")  # only to get an entry in ax2 legend
    ax42.plot(results_df["t"], results_df["RQ"], label="RQ", color=blau)
    ax42.set_ylabel("RQ [-]", fontsize=labelsize, color=schwarz)
    ax42.set_ylim(bottom=0)
    ax4.legend()
    ax4.set_title("Abgasanalyse", fontsize=labelsize + 3)
    # # plt.xlabel("t in h",fontsize=labelsize)
    # # plt.ylabel("$c_{S}$, $c_{x}$ in $g \cdot L^{-1}$",fontsize=labelsize)
    # # plt.tick_params(axis="both", labelsize=int(0.85*labelsize))
    # plt.legend()
    fig.tight_layout()
    plt.show()
    return ()

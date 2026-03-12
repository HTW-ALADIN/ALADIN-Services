import json
import logging
import pathlib

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp  # solve odes

from calc.Fx_ODE_Bioreaktor import (
    Bioreaktor_ODE,
)  # hier wird das Differentialgleichungssystem definiert
from calc.Nebenrechnungen import Nebenrechnungen
from DataModels.input_definition import InputKeys

MODEL_PATH = pathlib.Path(__file__).parent.parent / "DataModels" / "model_db.json"


def calculate(ferm_param_in_df: pd.DataFrame) -> pd.DataFrame:
    try:
        model_id = str(
            int(ferm_param_in_df[InputKeys.model.value][0])
        )  # model_id is a string! if read from excel model number is a float64
        logging.info(f" Model {model_id} is being used.")
        with open(MODEL_PATH) as f:
            model = json.load(f)
            model_param_in = model[model_id]  # dictionary

    except json.JSONDecodeError:
        logging.error("Invalid JSON input in Model_db.json.")
        raise
    except FileNotFoundError as error:
        logging.error("Invalid file path for Model_db.json.")
        logging.error(error)
        raise

    # Nebenberechnung
    [model_param, ferm_param_df] = Nebenrechnungen(model_param_in, ferm_param_in_df)
    # global constants
    data_rate = 60  # data rate per hour
    Vm_norm = 22.41396954  # molares Volumen in NL/mol bei Normbedingungen (0°C und 101,325 kPa)
    c_O2_Luft = 0.2095  # Sauerstoffgehalt Luft in mol(O2)/mol(Luft)
    c_CO2_Luft = 0.0004147  # CO2 Gehalt der Luft in mol(CO2)/mol(Luft)

    # nachfolgend Hauptberechnung
    for index, row in ferm_param_df.iterrows():
        # result_df hier befüllen
        logging.debug(f" Phase: {row[InputKeys.phase]}")
        # Set the starting conditions for solving the ODEs
        if index == 0:
            c_x_0 = row[InputKeys.c_x0]
            c_S1_0 = row[InputKeys.bolus_c]
            c_S2_0 = row[InputKeys.bolus_n]
            c_P_0 = 0
            c_DO_0 = row[InputKeys.c_o2_sat] * row[InputKeys.do] / 100

            y0 = [
                c_x_0,
                c_S1_0,
                c_S2_0,
                c_P_0,
                c_DO_0,
                c_O2_Luft,
                c_CO2_Luft,
            ]  # Startparameter in Vektor
            t_start = 0
            t_ende = row[InputKeys.duration]

        else:
            c_x_0 = y[-1, 0]  # noqa: F821  # "-1" means the last element of the array
            c_S1_0 = y[-1, 1] + row[InputKeys.bolus_c]  # noqa: F821
            c_S2_0 = y[-1, 2] + row[InputKeys.bolus_n]  # noqa: F821
            c_P_0 = y[-1, 3]  # noqa: F821
            logging.debug(f"c_P0: {c_P_0}")
            logging.debug(f"c_x: {c_x_0}")
            c_DO_0 = y[-1, 4]  # noqa: F821
            O2_Out = y[-1, 5]  # noqa: F821  # Konz. O2 in Abluft
            CO2_Out = y[-1, 6]  # noqa: F821  # Konz. CO2 in Abluft
            y0 = [
                c_x_0,
                c_S1_0,
                c_S2_0,
                c_P_0,
                c_DO_0,
                O2_Out,
                CO2_Out,
            ]  # Startparameter in Vektor
            t_start = result.t[-1]  # noqa: F821
            t_ende = t_start + row[InputKeys.duration]

        if row[InputKeys.duration] != 0:  # only proceed if the duration is not 0
            logging.info(f"Calc Phase: {index} from {t_start} - {t_ende} h")
            datapoints = int(row[InputKeys.duration] * data_rate)  # make sure datapoints is an integer
            t_span = np.linspace(t_start, t_ende, datapoints)
            if datapoints < 50:
                datapoints = (
                    50  # this is needed in case a Phase is really short so the minimal number of datapoint per phase=50
                )
            Fpar_d = row.to_dict()  # extract Fermentation parameters for current phase and convert to dictionary as this is faster in solve_ivp

            result = solve_ivp(
                Bioreaktor_ODE,
                (t_start, t_ende),
                y0,
                args=(model_param, Fpar_d),
                t_eval=t_span,
                max_step=0.0005,
                atol=1e-6,
                rtol=1e-7,
            )
            # solve_IVP Explanations
            # args are passed as a tupel - a single element in a tupel is single_element_tuple = (5,)
            # via small atol and rtol practical "non-negative" is achieved
            # Results of Solve_ivp stores y values in result.y which is an array of one row per parameter
            # and n-datapoints in n columns
            if index == 0:
                y = result.y.T
                y_ges = y  # transform array
                logging.debug(f" dim y_ges: {y_ges.shape}")
                t_ges = np.atleast_2d(result.t).T
                logging.debug(f" dim t_ges: {t_ges.shape}")
                sum_feeding = t_span * row[InputKeys.feed_c]
                len_t_span = len(t_span)
                Drehzahl = np.zeros(len_t_span) + row[InputKeys.rpm]
                Q_Air = np.zeros(len_t_span) + row[InputKeys.q_air]
                Druck = np.zeros(len_t_span) + row[InputKeys.pressure]
            else:
                y = result.y.T  # transform array
                y_ges = np.vstack((y_ges, y))
                t = np.atleast_2d(result.t).T
                t_ges = np.vstack((t_ges, t))
                already_fed = sum_feeding[-1]
                t_span_temp = np.subtract(t_span, t_span[0])
                temp_feed = already_fed + t_span_temp * row[InputKeys.feed_c]
                sum_feeding = np.hstack((sum_feeding, temp_feed))
                len_t_span = len(t_span)
                Drehzahl = np.hstack((Drehzahl, np.zeros(len_t_span) + row[InputKeys.rpm]))
                Q_Air = np.hstack((Q_Air, np.zeros(len_t_span) + row[InputKeys.q_air]))
                Druck = np.hstack((Druck, np.zeros(len_t_span) + row[InputKeys.pressure]))

    #######################################
    # #Weitere Variablen berechnen
    #######################################
    V_L = np.zeros(len(t_ges)) + ferm_param_df[InputKeys.start_vol][0]  # Platzhalter für Fermentationsvolumen in L
    Begasungsrate = Q_Air / V_L
    c_ox_sat_DO = ferm_param_df[InputKeys.c_o2_sat][
        0
    ]  # Sauerstofflöslichkeit zu Beginn der Fermentation um DO zu berechnen
    c_inert_Luft = 1 - c_O2_Luft - c_CO2_Luft  # Inertgasanteil der Luft
    c_inert_Abgas = np.zeros(len(t_ges)) + 1
    c_inert_Abgas = c_inert_Abgas - y_ges[:, 5]
    c_inert_Abgas = c_inert_Abgas - y_ges[:, 6]
    delta_O2 = np.zeros(len(t_ges)) + c_O2_Luft
    delta_O2 = delta_O2 - y_ges[:, 5] * c_inert_Luft / c_inert_Abgas
    OUR = 1000 * (
        (Begasungsrate * 60) / Vm_norm * delta_O2 + 1 * 10 ** (-10)
    )  # %Oxygen Uptake Rate in mmol*L-1*h-1, last addition to avoid div by zero

    delta_CO2 = np.zeros(len(t_ges)) - c_CO2_Luft
    delta_CO2 = delta_CO2 + y_ges[:, 6] * c_inert_Luft / c_inert_Abgas
    CER = 1000 * ((Begasungsrate * 60) / Vm_norm * delta_CO2)  # Carbon Dioxide Evolution Rate in mmol*L-1*h-1

    RQ = CER / OUR
    c_DO_proz = y_ges[:, 4] / c_ox_sat_DO * 100

    # put results of solve_ivp into a dataframelation_finished")
    logging.debug("calculation_finished")
    # stack 1D Arrays together
    calc = np.column_stack((sum_feeding, Begasungsrate, Drehzahl, Druck, OUR, CER, RQ, c_DO_proz, V_L))
    logging.debug(f"result data shape: {calc.shape}")
    results_columns = [
        "t",
        "c_x",
        "c_S1",
        "c_S2",
        "c_P",
        "c_DO",
        "c_O2_Out",
        "c_CO2_Out",
        "Sum_Feed",
        "Begasungsrate",
        "Drehzahl",
        "Druck",
        "OUR",
        "CER",
        "RQ",
        "c_DO_proz",
        "V_L",
    ]
    results = np.hstack(
        (np.array(np.atleast_2d(t_ges)), np.array(y_ges), calc)
    )  # atleast_2d makes sure that the array has a 2nd dimension

    result_df = pd.DataFrame(data=results, columns=results_columns)

    return result_df

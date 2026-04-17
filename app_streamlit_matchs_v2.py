import math
from pathlib import Path
from collections import defaultdict

import streamlit as st
import pandas as pd

@st.cache_data
def load_data(uploaded_file):
    resultats = pd.read_excel(uploaded_file, sheet_name="Resultats", engine="openpyxl")
    details = pd.read_excel(uploaded_file, sheet_name="Matchs", engine="openpyxl")
    return resultats, details

st.set_page_config(page_title="Stats Matchs", layout="wide")

uploaded_file = st.file_uploader("Dépose ton fichier Excel", type=["xlsx"])

if uploaded_file is None:
    st.info("Ajoute un fichier Excel pour afficher les données.")
    st.stop()

resultats_df, details_df = load_data(uploaded_file)


def normalize_name(name):
    if pd.isna(name) or name is None:
        return None
    name = str(name).strip()
    return ALIASES.get(name, name)


@st.cache_data

def load_data(file_path: Path):
    resultats = pd.read_excel(file_path, sheet_name="Resultats")
    matchs = pd.read_excel(file_path, sheet_name="Matchs")

    resultats.columns = [str(c).strip() for c in resultats.columns]
    matchs.columns = [str(c).strip() for c in matchs.columns]

    resultats["Date"] = pd.to_datetime(resultats["Date"], errors="coerce")
    resultats["Adversaire"] = resultats["Adversaire"].astype(str).str.strip()
    resultats["Score"] = resultats["Score"].astype(str).str.strip()
    resultats["Competition"] = resultats["Competition"].fillna("Non renseignée").astype(str).str.strip()
    resultats["MVP"] = resultats["MVP"].fillna("").astype(str).str.strip()

    # Parse du score pour extraire buts marqués / encaissés
    gf, ga = [], []
    for score in resultats["Score"]:
        parts = str(score).split("-")
        if len(parts) == 2:
            try:
                gf.append(int(parts[0].strip()))
                ga.append(int(parts[1].strip()))
            except ValueError:
                gf.append(None)
                ga.append(None)
        else:
            gf.append(None)
            ga.append(None)
    resultats["Buts marqués"] = gf
    resultats["Buts encaissés"] = ga

    def get_result_label(row):
        if pd.isna(row["Buts marqués"]) or pd.isna(row["Buts encaissés"]):
            return "N/A"
        if row["Buts marqués"] > row["Buts encaissés"]:
            return "Victoire"
        if row["Buts marqués"] < row["Buts encaissés"]:
            return "Défaite"
        return "Nul"

    resultats["Résultat"] = resultats.apply(get_result_label, axis=1)

    # Liste des MVP pour chaque match
    resultats["MVP_list"] = resultats["MVP"].apply(
        lambda x: [normalize_name(n) for n in str(x).split(",") if str(n).strip()]
    )

    # --- Parsing de la feuille Matchs par blocs ---
    rows = []
    current_match = None
    match_occurrence = defaultdict(int)

    for _, row in matchs.iterrows():
        match_name = row.get("Match")
        player = row.get("Joueurs présents")
        goals = row.get("But(s)")
        assists = row.get("Passe(s) dé(s)")

        # Nouvelle entête de bloc match
        if pd.notna(match_name):
            current_match = str(match_name).strip()
            match_occurrence[current_match] += 1
            current_occurrence = match_occurrence[current_match]
        elif current_match is None:
            continue

        # Ligne vide entre deux blocs
        if pd.isna(player):
            continue

        goals = 0 if pd.isna(goals) else int(goals)
        assists = 0 if pd.isna(assists) else int(assists)
        player = normalize_name(player)

        rows.append(
            {
                "Adversaire": current_match,
                "Occurrence": current_occurrence,
                "Joueur": player,
                "Buts": goals,
                "Passes décisives": assists,
            }
        )

    details = pd.DataFrame(rows)

    # On relie les résultats et les détails par adversaire + numéro d'occurrence
    resultats = resultats.sort_values("Date").reset_index(drop=True)
    resultats["Occurrence"] = resultats.groupby("Adversaire").cumcount() + 1
    resultats["match_id"] = resultats.index + 1

    details = details.merge(
        resultats[["match_id", "Adversaire", "Occurrence", "Date", "Score", "Competition", "Résultat", "MVP_list"]],
        on=["Adversaire", "Occurrence"],
        how="left",
    )

    # Ajout du statut MVP par joueur pour chaque match
    details["MVP du match"] = details.apply(
        lambda r: "Oui" if isinstance(r["MVP_list"], list) and r["Joueur"] in r["MVP_list"] else "Non",
        axis=1,
    )

    return resultats, details


resultats_df, details_df = load_data(FILE_PATH)


# -------------------------------
# Sidebar
# -------------------------------
st.sidebar.title("⚙️ Filtres")
competitions = ["Toutes"] + sorted(resultats_df["Competition"].dropna().unique().tolist())
competition_selected = st.sidebar.selectbox("Compétition", competitions)

adversaires = ["Tous"] + sorted(resultats_df["Adversaire"].dropna().unique().tolist())
adversaire_selected = st.sidebar.selectbox("Adversaire", adversaires)

filtered_resultats = resultats_df.copy()
if competition_selected != "Toutes":
    filtered_resultats = filtered_resultats[filtered_resultats["Competition"] == competition_selected]
if adversaire_selected != "Tous":
    filtered_resultats = filtered_resultats[filtered_resultats["Adversaire"] == adversaire_selected]


# -------------------------------
# Header
# -------------------------------
st.title("⚽ Consultation des matchs et statistiques joueurs")
st.caption("Application Streamlit basée sur le fichier Stats_matchs.xlsx")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Nombre de matchs", len(filtered_resultats))
col2.metric("Buts marqués", int(filtered_resultats["Buts marqués"].fillna(0).sum()))
col3.metric("Buts encaissés", int(filtered_resultats["Buts encaissés"].fillna(0).sum()))
col4.metric("Différence de buts", int(filtered_resultats["Buts marqués"].fillna(0).sum() - filtered_resultats["Buts encaissés"].fillna(0).sum()))

onglet_matchs, onglet_joueurs, onglet_stats = st.tabs(["Matchs", "Joueurs", "Statistiques"])


# -------------------------------
# Onglet Matchs
# -------------------------------
with onglet_matchs:
    st.subheader("Résultats des matchs")

    affichage_matchs = filtered_resultats[["Date", "Adversaire", "Competition", "Score", "Résultat", "MVP"]].copy()
    affichage_matchs["Date"] = affichage_matchs["Date"].dt.strftime("%d/%m/%Y")
    st.dataframe(affichage_matchs, use_container_width=True, hide_index=True)

    if filtered_resultats.empty:
        st.info("Aucun match ne correspond aux filtres sélectionnés.")
    else:
        st.markdown("### Détail d'un match")

        match_options = filtered_resultats.copy()
        match_options["label"] = match_options.apply(
            lambda r: f"{r['Date'].strftime('%d/%m/%Y')} - {r['Adversaire']} ({r['Score']})",
            axis=1,
        )

        selected_label = st.selectbox("Choisir un match", match_options["label"].tolist())
        selected_match = match_options.loc[match_options["label"] == selected_label].iloc[0]

        st.markdown(
            f"**Date :** {selected_match['Date'].strftime('%d/%m/%Y')}  \\\n**Adversaire :** {selected_match['Adversaire']}  \\\n**Compétition :** {selected_match['Competition']}  \\\n**Score :** {selected_match['Score']}  \\\n**MVP :** {selected_match['MVP'] if selected_match['MVP'] else 'Non renseigné'}"
        )

        details_match = details_df[details_df["match_id"] == selected_match["match_id"]].copy()
        details_match = details_match[["Joueur", "Buts", "Passes décisives", "MVP du match"]]
        details_match = details_match.sort_values(["Buts", "Passes décisives", "Joueur"], ascending=[False, False, True])

        st.markdown("#### Joueurs présents et statistiques")
        st.dataframe(details_match, use_container_width=True, hide_index=True)


# -------------------------------
# Onglet Joueurs
# -------------------------------
with onglet_joueurs:
    st.subheader("Statistiques individuelles")

    joueurs = sorted(details_df["Joueur"].dropna().unique().tolist())
    joueur_selected = st.selectbox("Choisir un joueur", joueurs)

    joueur_df = details_df[details_df["Joueur"] == joueur_selected].copy()

    nb_matchs = len(joueur_df)
    total_buts = int(joueur_df["Buts"].sum())
    total_passes = int(joueur_df["Passes décisives"].sum())
    total_mvp = int((joueur_df["MVP du match"] == "Oui").sum())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Matchs joués", nb_matchs)
    k2.metric("Buts", total_buts)
    k3.metric("Passes décisives", total_passes)
    k4.metric("MVP", total_mvp)

    st.markdown("### Historique des matchs du joueur")
    historique = joueur_df[["Date", "Adversaire", "Competition", "Score", "Résultat", "Buts", "Passes décisives", "MVP du match"]].copy()
    historique["Date"] = pd.to_datetime(historique["Date"]).dt.strftime("%d/%m/%Y")
    historique = historique.sort_values("Date")
    st.dataframe(historique, use_container_width=True, hide_index=True)

    st.markdown("### Tableau récapitulatif de tous les joueurs")
    resume_joueurs = (
        details_df.groupby("Joueur", as_index=False)
        .agg(
            **{
                "Matchs joués": ("match_id", "count"),
                "Buts": ("Buts", "sum"),
                "Passes décisives": ("Passes décisives", "sum"),
                "MVP": ("MVP du match", lambda s: (s == "Oui").sum()),
            }
        )
        .sort_values(["Buts", "Passes décisives", "MVP", "Matchs joués"], ascending=[False, False, False, False])
        .reset_index(drop=True)
    )
    st.dataframe(resume_joueurs, use_container_width=True, hide_index=True)


# -------------------------------
# Onglet Statistiques
# -------------------------------
with onglet_stats:
    st.subheader("Classements individuels")

    stats_filtrees = details_df.copy()
    if competition_selected != "Toutes":
        stats_filtrees = stats_filtrees[stats_filtrees["Competition"] == competition_selected]
    if adversaire_selected != "Tous":
        stats_filtrees = stats_filtrees[stats_filtrees["Adversaire"] == adversaire_selected]

    classement_joueurs = (
        stats_filtrees.groupby("Joueur", as_index=False)
        .agg(
            **{
                "Matchs joués": ("match_id", "count"),
                "Buts": ("Buts", "sum"),
                "Passes décisives": ("Passes décisives", "sum"),
                "MVP": ("MVP du match", lambda s: (s == "Oui").sum()),
            }
        )
        .sort_values(["Buts", "Passes décisives", "MVP", "Matchs joués", "Joueur"], ascending=[False, False, False, False, True])
        .reset_index(drop=True)
    )

    if classement_joueurs.empty:
        st.info("Aucune statistique disponible avec les filtres sélectionnés.")
    else:
        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown("### 🥇 Meilleurs buteurs")
            top_buteurs = (
                classement_joueurs[["Joueur", "Buts", "Matchs joués"]]
                .sort_values(["Buts", "Matchs joués", "Joueur"], ascending=[False, False, True])
                .reset_index(drop=True)
            )
            top_buteurs.index = top_buteurs.index + 1
            st.dataframe(top_buteurs, use_container_width=True)

        with c2:
            st.markdown("### 🎯 Meilleurs passeurs")
            top_passeurs = (
                classement_joueurs[["Joueur", "Passes décisives", "Matchs joués"]]
                .sort_values(["Passes décisives", "Matchs joués", "Joueur"], ascending=[False, False, True])
                .reset_index(drop=True)
            )
            top_passeurs.index = top_passeurs.index + 1
            st.dataframe(top_passeurs, use_container_width=True)

        with c3:
            st.markdown("### 👑 Classement des MVP")
            top_mvp = (
                classement_joueurs[["Joueur", "MVP", "Matchs joués"]]
                .sort_values(["MVP", "Matchs joués", "Joueur"], ascending=[False, False, True])
                .reset_index(drop=True)
            )
            top_mvp.index = top_mvp.index + 1
            st.dataframe(top_mvp, use_container_width=True)

        st.markdown("### Classement général")
        classement_general = classement_joueurs.sort_values(
            ["Buts", "Passes décisives", "MVP", "Matchs joués", "Joueur"],
            ascending=[False, False, False, False, True],
        ).reset_index(drop=True)
        classement_general.index = classement_general.index + 1
        st.dataframe(classement_general, use_container_width=True)


with st.expander("Voir le code à adapter pour ton propre fichier"):
    st.code(
        """
# Pour lancer l'application dans le terminal :
streamlit run app_streamlit_matchs.py
        """.strip(),
        language="bash",
    )

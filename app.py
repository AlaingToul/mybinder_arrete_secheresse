# -*- coding: utf-8 -*----------------------------------------------------------
# Name:        app.py
# Purpose:     Construction et présentation de la carte de suivi des
#              arrêtés sécheresse en vigueur pour les eaux superficielles
#
# Author:      Alain Gauthier
#
# Created:     30/04/2025
# Licence:     GPL V3
#-------------------------------------------------------------------------------

import io
import os
import ast
import json
import datetime as dt
import dateutil
import dateutil.relativedelta
import requests
import pandas as pd
import geopandas as gpd
import folium
import streamlit as st

from streamlit_folium import st_folium

import branca as bc

# dossier racine où se trouvent les données récupérées et à présenter
Racine = "./donnees"

#-------------------------------------------------------------------------------

def get_zones_secheresse(uploaded_file):
    """Requête de récupération des zones d'arrêté sécheresse.
    Renvoie uniquement les zones de type 'SUP' pour les eaux superficielles

    Args:
        uploaded_file: fichier GeoJSON ou ZIP contenant les données

    Returns:
        geoDataFrame: zones filtrées sur le type 'SUP'
    """
    # pour savoir si réunifier les tuiles
    traiter_pmtiles = False
    if uploaded_file is not None:
        # lecture du fichier GeoJSON ou ZIP
        st.sidebar.markdown(f"## Fichier à lire : {uploaded_file.name}")
        zones_arretes = lire_geopandas(uploaded_file)
    else:
        # URL stable de la couche
        #url_zones_arretes = "https://www.data.gouv.fr/fr/datasets/r/bfba7898-aed3-40ec-aa74-abb73b92a363"
        # URL stable de la couche au format PMTiles
        url_zones_arretes = "https://object.files.data.gouv.fr/hydra-pmtiles/hydra-pmtiles/bfba7898-aed3-40ec-aa74-abb73b92a363.pmtiles"

        # requête du fichier
        st.sidebar.markdown(f"## Requête auprès de : {url_zones_arretes}")
        rep = requests.get(url_zones_arretes)

        fio = io.BytesIO(rep.content)
        # dans geopandas
        zones_arretes = gpd.read_file(fio)
        traiter_pmtiles = True

    # on ne garde que le type 'SUP'
    zones_arretes = zones_arretes[zones_arretes["type"] == "SUP"]

    # pour le traitement des tuiles pmtiles : il faut fusionner les polygones par id
    if traiter_pmtiles:
        zones_arretes = zones_arretes.dissolve(by='id', aggfunc='first')

    # gestion du code de département des zones d'arrêtés
    zones_arretes['insee_dept'] = zones_arretes['departement'].apply(lambda x: json.loads(x)['code'])

    # filtre pour ne conserver que l'affichage des départements de métropole (longueur de code dept < 3)
    zones_arretes = zones_arretes.where(zones_arretes["insee_dept"].apply(lambda x:len(x)<3))
    zones_arretes = zones_arretes.dropna(axis=0, subset='insee_dept')

    # ajout de l'information du lien vers l'arrêté en fichier pdf
    zones_arretes['chemin_fichier'] = zones_arretes['arreteRestriction'].apply(lambda x: json.loads(x)['fichier'])
    # fin
    return zones_arretes

#-------------------------------------------------------------------------------

@st.cache_data
def lire_geopandas(fic_couche):
    """lecture de la couche depuis le fichier passé en paramètre.
    Activation du cache dans l'application Streamlit

    Args:
        fic_couche (str): nom de fichier local à lire

    Returns:
        GeoDataFrame: couche lue
    """
    gdf = gpd.read_file(fic_couche)
    return gdf

#-------------------------------------------------------------------------------

@st.cache_data
def get_arretes():
    """Requête de récupération des arrêtés de restriction archivés

    Returns:
        DataFrame: tableau des arrêtés récupérés
    """
    # url des archives des arrêtés
    url_arretes = "https://www.data.gouv.fr/fr/datasets/r/f425cfa6-ccd1-438e-bb03-9d90ab527851"

    # requête du fichier
    rep = requests.get(url_arretes)

    # chargement des données dans un dataframe
    fio = io.BytesIO(rep.content)

    # avec analyse des dates sur 3 colonnes
    df_arretes = pd.read_csv(fio,sep=',')
    df_arretes = df_arretes.dropna(axis=0,how='any', subset='date_fin')
    # fin
    return df_arretes

#-------------------------------------------------------------------------------

def _categorical_legend(m, title, categories, colors):
    """
    MODIFICATION POUR POSITIONNER LA LEGENDE
    FONCTION D'ORIGINE DANS geopandas/explore.py

    --> CHANGEMENT : postition par rapport au coin (left, top) au lieu de (right, bottom)

    Add categorical legend to a map

    The implementation is using the code originally written by Michel Metran
    (@michelmetran) and released on GitHub
    (https://github.com/michelmetran/package_folium) under MIT license.

    Copyright (c) 2020 Michel Metran

    Parameters
    ----------
    m : folium.Map
        Existing map instance on which to draw the plot
    title : str
        title of the legend (e.g. column name)
    categories : list-like
        list of categories
    colors : list-like
        list of colors (in the same order as categories)
    """

    # Header to Add
    head = """
    {% macro header(this, kwargs) %}
    <script src="https://code.jquery.com/ui/1.12.1/jquery-ui.js"></script>
    <script>$( function() {
        $( ".maplegend" ).draggable({
            start: function (event, ui) {
                $(this).css({
                    right: "auto",
                    top: "auto",
                    bottom: "auto"
                });
            }
        });
    });
    </script>
    <style type='text/css'>
      .maplegend {
        position: absolute;
        z-index:9999;
        background-color: rgba(255, 255, 255, .8);
        border-radius: 5px;
        box-shadow: 0 0 15px rgba(0,0,0,0.2);
        padding: 10px;
        font: 12px/14px Arial, Helvetica, sans-serif;
        left: 10px;
        top: 120px;
      }
      .maplegend .legend-title {
        text-align: left;
        margin-bottom: 5px;
        font-weight: bold;
        }
      .maplegend .legend-scale ul {
        margin: 0;
        margin-bottom: 0px;
        padding: 0;
        float: left;
        list-style: none;
        }
      .maplegend .legend-scale ul li {
        list-style: none;
        margin-left: 0;
        line-height: 16px;
        margin-bottom: 2px;
        }
      .maplegend ul.legend-labels li span {
        display: block;
        float: left;
        height: 14px;
        width: 14px;
        margin-right: 5px;
        margin-left: 0;
        border: 0px solid #ccc;
        }
      .maplegend .legend-source {
        color: #777;
        clear: both;
        }
      .maplegend a {
        color: #777;
        }
    </style>
    {% endmacro %}
    """

    # Add CSS (on Header)
    macro = bc.element.MacroElement()
    macro._template = bc.element.Template(head)
    m.get_root().add_child(macro)

    body = f"""
    <div id='maplegend {title}' class='maplegend'>
        <div class='legend-title'>{title}</div>
        <div class='legend-scale'>
            <ul class='legend-labels'>"""

    # Loop Categories
    for label, color in zip(categories, colors):
        body += f"""
                <li><span style='background:{color}'></span>{label}</li>"""

    body += """
            </ul>
        </div>
    </div>
    """

    # Add Body
    body = bc.element.Element(body, "legend")
    m.get_root().html.add_child(body)

#-------------------------------------------------------------------------------

def construire_carte(itineraire, zones_arrete, dept_iti, uploaded_file):
    """construction de la carte folium basée sur les deux couches passées en paramètre

    Args:
        itineraire (GeoDataFrame): couche des itinéraires COP
        zones_arrete (GeoDataFrame): couche des zones de sécheresse à afficher
        dept_iti (GeoDataFrame): couche des départements en lien avec le réseau de VNF
        uploaded_file (UploadedFile): fichier téléchargé contenant les données

    Returns:
        map: instance de carte folium
    """

    # copie locale
    czones_arrete = gpd.GeoDataFrame(zones_arrete)

    # codes couleur des zones d'arrêtés selon le niveau de gravité
    niveaux  = ["vigilance", "alerte",  "alerte renforcée", "crise"]
    couleurs = ["#ffeda0",   "#feb24c", "#fc4e2a", "#b10026"]
    # assignation avec l'intermédiaire des codes de niveau
    codes_niveau = ["vigilance", "alerte",  "alerte_renforcee", "crise"]
    czones_arrete["couleur"] = czones_arrete["niveauGravite"].map(dict(zip(codes_niveau,couleurs)))

    # carte centrée sur ce point choisi manuellement
    centre = [46.463,2.661]
    # limites : celle des itinéraires
    bounds =itineraire.total_bounds
    attr = (
        '&copy; OpenStreetMap France | &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    )

    carte = folium.Map(
        location=centre,
        #attr=attr,
        tiles= "OpenStreetMap", # "https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png",
    )

    carte.fit_bounds([[bounds[1],bounds[0]],
                      [bounds[3],bounds[2]]])

    # ajout de la couche départements
    folium.GeoJson(dept_iti,
                  name="Départements réseau VNF",
                  style_function=lambda x: {"color": "#c0c0c0", "weight": 2},
                  ).add_to(carte)

    # ajout des zones d'arrêté avec contrôle de la légende
    czones_arrete.explore(m=carte,
        column='niveauGravite',
        tooltip=['niveauGravite', 'departement'],
        categorical=True,
        categories=codes_niveau,
        k=len(codes_niveau),
        cmap=couleurs,
        popup=True,
        legend=False,
        name= "Zones d'arrêtés sécheresse",
        )

    # légende "à la main" issue de la fonction d'explore,
    # mais avec positionnement adapté à cette carte
    _categorical_legend(carte,
                        title='Niveau de gravité',
                        categories=niveaux,
                        colors=couleurs)

    # ajout de la couche itinéraire
    folium.GeoJson(itineraire,
                  name="Itinéraire COP",
                  style_function=lambda x: {"color": "#0000ff", "weight": 2},
                  ).add_to(carte)

    # ajout du titre de la carte
    # la date est connue seulement si les données ont été téléchargées directement depuis le site, pas si c'est un fichier téléchargé
    if uploaded_file is None:
        title_html = f'''
        <h3 align="center" style="font-size:20px"><b>Zones d'arrêtés sécheresse</b>
        en date du {dt.date.today().strftime("%d/%m/%Y")}</h3>
                '''
    else:
        title_html = '''
        <h3 align="center" style="font-size:20px"><b>Zones d'arrêtés sécheresse</b>
        </h3>
                '''

    carte.get_root().html.add_child(folium.Element(title_html))

    # ajout du contrôle des couches
    folium.map.LayerControl().add_to(carte)

    # fin
    return carte

#-------------------------------------------------------------------------------

def safe_literal_eval(value):
    """Encapsulation de la fonction ast.literal_eval pour convertir la représentation en str
    d'une liste de valeurs ou une seule valeur en liste

    Args:
        value (str): valeur à convertir, supposée de la forme "[v1,v2,...]" ou simplement "v1"

    Returns:
        list: liste contenant les données extraites du paramètre d'entrée
    """
    try:
        # Essayer de convertir en liste
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        # Si échec, retourner une liste avec la valeur unique
        return [value]

#-------------------------------------------------------------------------------

def calculer_dept_arretes_date(df_arretes, date_compar, niveaux):
    """Calcul du nombre de départements ayant des arrêtés de restriction en eau superficielle
    en date passée en paramètre et pour les niveaux parmi la liste passée en paramètre.

    Args:
        df_arretes (DataFrame): archives des arrêtés à analyser
        date_compar (str): date de rechercher des arrêtés au format iso (yyyy-mm-dd)
        niveaux (list): liste des niveaux à conserver parmi les niveaux de gravité des arrêtés
    """

    # initialisation
    resultat = 0

    # filtre dates : l'arrêté doit être valide au moment de la date de recherche
    loc_df_arretes = df_arretes[df_arretes['date_debut'] < date_compar]
    if not loc_df_arretes.empty:
        loc_df_arretes = loc_df_arretes[loc_df_arretes['date_fin'] > date_compar]

    # préparation pour séparer les listes de zones d'arrêtés concernées
    if not loc_df_arretes.empty:
        loc_df_arretes["zones_alerte.niveau_gravite"] = \
            loc_df_arretes["zones_alerte.niveau_gravite"].apply(safe_literal_eval)
        loc_df_arretes['zones_alerte.type'] = \
            loc_df_arretes["zones_alerte.type"].apply(safe_literal_eval)
        # séparation des listes : en une entrée par valeur pour les deux colonnes à travailler
        loc_df_arretes = \
            loc_df_arretes.explode(['zones_alerte.niveau_gravite','zones_alerte.type'],
                                   ignore_index=True)

    # filtre zones_alerte.type : SUP pour les eaux superficielles
    if not loc_df_arretes.empty:
        loc_df_arretes = loc_df_arretes[loc_df_arretes['zones_alerte.type']=='SUP']

    # non vigilance
    if not loc_df_arretes.empty:
        df_arretes_non_vigi = \
            loc_df_arretes[loc_df_arretes["zones_alerte.niveau_gravite"].isin(niveaux)]

        # nombre de départements au delà de la vigilance
        if not df_arretes_non_vigi.empty:
            resultat = len(df_arretes_non_vigi['departement'].unique())
    # fin
    return resultat

#-------------------------------------------------------------------------------

def calculer_dept_arretes_an_passe(df_arretes):
    """Calcul du nombre de départements au delà de vigilance en année n-1
    au début du même mois que l'année courante.

    Args:
        df_arretes (DataFrame): archives des arrêtés à analyser
    """
    # initialisation
    resultat = 0
    # Détermination de l'année passée, début du même mois
    date_today = dt.date.today()
    an_moins_1 = date_today.year-1
    date_compar = dt.date(an_moins_1,date_today.month,1).isoformat()
    # recherche sur tous les niveaux sauf vigilance
    niveaux = ["alerte",  "alerte renforcée", "crise"]
    resultat = calculer_dept_arretes_date(df_arretes, date_compar, niveaux)
    # fin
    return resultat

#-------------------------------------------------------------------------------

def calculer_dept_zone_restrict(zones_arretes):
    """Calcul du nombre de départements des zones d'arrêtés de restriction hors niveau
    de vigilance

    Args:
        zones_arretes (geoDataFrame): couche des zones d'arrêtés de restriction

    Returns:
        int: nombre de département correspondant au critère recherché
    """
    # initialisation
    resultat = 0
    # zones d'arrêtés de restriction au delà de la vigilance
    zones_non_vigilance = zones_arretes[zones_arretes['niveauGravite'] != "vigilance"]

    # les départements correspondant à ces zones d'arrêtés
    if not zones_non_vigilance.empty:
        dept_res = zones_non_vigilance['insee_dept'].unique()
        # nb de départements trouvés
        resultat = len(dept_res)
    # fin
    return resultat

#-------------------------------------------------------------------------------

def calculer_dept_zone_vnf_niveau(zones_arretes, dept_iti, niveau):
    """Calcul du nombre de départements du réseau VNF ayant des zones
    d'arrêté au niveau de gravité recherché.

    Args:
        zones_arretes (geoDataFrame): couche des zones d'arrêté de restriction à analyser
        dept_iti (geoDataFrame): couche des départements du réseau VNF
        (paramètre structurel fixé n'évoluant pas dans le temps)
        niveau (str): chaîne de caractère indiquant le niveau de gravité à analyser.
        Attention aux fautes de frappe...c'est du texte !

    Returns:
        (int,str): (nombre, noms) des départements du réseau VNF ayant une zone de restriction dans
        le niveau recherché
    """
    # initialisation :
    resultat = (0,'')

    # zones en niveau spécifique sur le réseau VNF
    zones_filtres = zones_arretes[zones_arretes['niveauGravite'] == niveau]

    # les départements correspondant à ces zones d'arrêtés
    if not zones_filtres.empty:
        dept_filtre = zones_filtres['insee_dept'].unique()

        # application du filtre
        dept_resultat = dept_iti[dept_iti["insee_dep"].isin(dept_filtre)]

        # résultat en nb de départements
        if not dept_resultat.empty:
            resultat = (len(dept_resultat), ", ".join(dept_resultat["nom"]))
    # fin
    return resultat

#-------------------------------------------------------------------------------

def construire_table_indic(df_arretes, zones_arretes, dept_iti):
    r"""Construction d'un dataframe contenant les indicateurs de nombre de
    départements en restriction à date donnée selon plusieurs critères.

    Lignes des moments du dataframe résultat :
    - 'annee_courante' : indicateurs à la date au moment du lancement du calcul
    - 'annee_precedente' : indicateurs au 1er du mois de l'année précédente de la date du calcul
    - 'mois_precedent' : indicateurs au 1er du mois précédent de la date du calcul

    Colonnes du dataframe résultat :
    - 'dept_fr' : nombre de départements en restriction au delà du niveau vigilance
    - 'dept_vnf_crise_code' : nombre de départements du réseau VNF en crise
    - 'dept_vnf_crise_nom' : liste des noms des départements du réseau VNF en crise
                            /!\ renseigné uniquement pour l'année courante
    - 'dept_vnf_ar_code' : nombre des départements du réseau VNF en alerte renforcée
    - 'dept_vnf_ar_nom' : liste des noms des départements du réseau VNF en alerte renforcée
                            /!\ renseigné uniquement pour l'année courante
    - 'dept_vnf_a_code' : nombre des départements du réseau VNF en alerte
    - 'dept_vnf_a_nom' : liste des noms des départements du réseau VNF en alerte
                            /!\ renseigné uniquement pour l'année courante
    - 'dept_vnf_vg_code' : nombre des départements du réseau VNF en vigilance
    - 'dept_vnf_vg_nom' : liste des noms des départements du réseau VNF en vigilance
                            /!\ renseigné uniquement pour l'année courante

    Args:
        df_arretes (geoDataFrame): couche des arrêtés de restriction
        zones_arretes (geoDataFrame): couche des zones des arrêtés de restriction en cours
        dept_iti (geoDataFrame): couche des départements du réseau VNF

    Returns:
        DataFrame: dataframe contenant le résultat avec une ligne le moment choisi d'analyse
        et en colonnes les critères choisis
    """
    # initialisation
    df_resultat = pd.DataFrame(columns=['dept_fr',
                                        'dept_vnf_crise_code',
                                        'dept_vnf_crise_nom',
                                        'dept_vnf_ar_code',
                                        'dept_vnf_ar_nom',
                                        'dept_vnf_a_code',
                                        'dept_vnf_a_nom',
                                        'dept_vnf_vg_code',
                                        'dept_vnf_vg_nom',
                                        ]
                               )
    # Année courante

    # nombre de départements n'étant pas en niveau vigilance
    nb_dept_r_z = calculer_dept_zone_restrict(zones_arretes)
    # nombre de départements du réseau VNF en crise et alerte renforcée
    nb_dept_vnf_crise = calculer_dept_zone_vnf_niveau(zones_arretes, dept_iti, 'crise')
    nb_dept_vnf_ar = calculer_dept_zone_vnf_niveau(zones_arretes, dept_iti, 'alerte_renforcee')
    nb_dept_vnf_a = calculer_dept_zone_vnf_niveau(zones_arretes, dept_iti, 'alerte')
    nb_dept_vnf_vg = calculer_dept_zone_vnf_niveau(zones_arretes, dept_iti, 'vigilance')


    # ajout au résultat
    df_resultat.loc['annee_courante'] = [nb_dept_r_z,
                                         nb_dept_vnf_crise[0],
                                         nb_dept_vnf_crise[1],
                                         nb_dept_vnf_ar[0],
                                         nb_dept_vnf_ar[1],
                                         nb_dept_vnf_a[0],
                                         nb_dept_vnf_a[1],
                                         nb_dept_vnf_vg[0],
                                         nb_dept_vnf_vg[1]
                                         ]

    # Année précédente

    # nombre de départements français avec des arrêtés en début de mois de l'année passée
    nb_dept_an_passe = calculer_dept_arretes_an_passe(df_arretes)

    # ajout au résultat
    df_resultat.loc['annee_precedente'] = [nb_dept_an_passe,
                                         0,
                                         '',
                                         0,
                                         '',
                                         0,
                                         '',
                                         0,
                                         '',
                                         ]

    # 1er jour du mois précédent (on fixe day=1 et on retranche 1 mois)
    date_compar = dt.date.today() + dateutil.relativedelta.relativedelta(months=-1, day=1)
    # recherche sur tous les niveaux sauf vigilance
    niveaux = ["alerte",  "alerte_renforcee", "crise"]
    nb_dept_r_z_mois_prec = calculer_dept_arretes_date(df_arretes, date_compar.isoformat(), niveaux)
    niveaux = ["crise"]
    nb_dept_vnf_crise_mois_prec = calculer_dept_arretes_date(df_arretes, date_compar.isoformat(), niveaux)
    niveaux = ["alerte_renforcee"]
    nb_dept_vnf_ar_mois_prec = calculer_dept_arretes_date(df_arretes, date_compar.isoformat(), niveaux)
    niveaux = ["alerte"]
    nb_dept_vnf_a_mois_prec = calculer_dept_arretes_date(df_arretes, date_compar.isoformat(), niveaux)
    niveaux = ["vigilance"]
    nb_dept_vnf_vg_mois_prec = calculer_dept_arretes_date(df_arretes, date_compar.isoformat(), niveaux)

    # ajout au résultat
    df_resultat.loc['mois_precedent'] = [nb_dept_r_z_mois_prec,
                                         nb_dept_vnf_crise_mois_prec,
                                         '',
                                         nb_dept_vnf_ar_mois_prec,
                                         '',
                                         nb_dept_vnf_a_mois_prec,
                                         '',
                                         nb_dept_vnf_vg_mois_prec,
                                         ''
                                         ]
    # fin
    return df_resultat

#-------------------------------------------------------------------------------

def inserer_indic_dept(table_indic):
    r"""Représentation des données du dataframe passé en paramètre.

    Lignes des moments du dataframe  :
    - 'annee_courante' : indicateurs à la date au moment du lancement du calcul
    - 'annee_precedente' : indicateurs au 1er du mois de l'année précédente de la date du calcul
    - 'mois_precedent' : indicateurs au 1er du mois précédent de la date du calcul

    Colonnes du dataframe  :
    - 'dept_fr' : nombre de départements en restriction au delà du niveau vigilance
    - 'dept_vnf_crise_code' : nombre de départements du réseau VNF en crise
    - 'dept_vnf_crise_nom' : liste des noms des départements du réseau VNF en crise
                            /!\ renseigné uniquement pour l'année courante
    - 'dept_vnf_ar_code' : nombre des départements du réseau VNF en alerte renforcée
    - 'dept_vnf_ar_nom' : liste des noms des départements du réseau VNF en alerte renforcée
                            /!\ renseigné uniquement pour l'année courante
    - 'dept_vnf_a_code' : nombre des départements du réseau VNF en alerte
    - 'dept_vnf_a_nom' : liste des noms des départements du réseau VNF en alerte
                            /!\ renseigné uniquement pour l'année courante
    - 'dept_vnf_vg_code' : nombre des départements du réseau VNF en vigilance
    - 'dept_vnf_vg_nom' : liste des noms des départements du réseau VNF en vigilance
                            /!\ renseigné uniquement pour l'année courante

    Args:
        table_indic (DataFrame): contient les indicateurs selon la strucure indiquée précédemment
    """

    def _signe_devant(valeur):
        signe=''
        if valeur>0:
            signe=r'\+ '
        if valeur<0:
            signe=r'\- '
        return signe


    # ajout du nombre de colonnes et lignes
    ligne1 = st.columns(1, border=True)
    ligne_vnf = st.columns(1, border=False)
    ligne2 = st.columns(4, border=True)
    ligne3 = st.columns(4, border=True)
    ligne4 = st.columns(4, border=True)

    # remplissage
    indic_annee_courante = table_indic.loc['annee_courante']
    indic_annee_prec = table_indic.loc['annee_precedente']
    indic_mois_prec = table_indic.loc['mois_precedent']
    # ligne1 : national
    ligne1[0].write(f"# :grey-background[{indic_annee_courante['dept_fr']}]")
    ligne1[0].write(":grey-background[départements en France avec des mesures\
                     de restrictions \ndes usages au-delà de la vigilance]")


    diff_indic_mois = indic_annee_courante['dept_fr'] - indic_mois_prec['dept_fr']
    signe=_signe_devant(diff_indic_mois)
    if signe == '':
        ligne1[0].write( "nombre de départements identique par rapport au mois dernier")
    else:
        ligne1[0].write(f"# {signe}{abs(diff_indic_mois)}")
        ligne1[0].write( "départements en arrêté par rapport au mois dernier")

    ligne1[0].write(f":grey-background[{indic_annee_prec['dept_fr']} en 2024]")

    # ligne entête VNF
    ligne_vnf[0].write("Sur le réseau VNF uniquement :")

    # ligne2
    ligne2[0].write(f"# {indic_annee_courante['dept_vnf_vg_code']}")
    ligne2[0].write("départements en vigilance]")
    ligne2[1].write(f"# {indic_annee_courante['dept_vnf_a_code']}")
    ligne2[1].write("départements en alerte]")
    ligne2[2].write(f"# {indic_annee_courante['dept_vnf_ar_code']}")
    ligne2[2].write("départements en alerte renforcée]")
    ligne2[3].write(f"# :red-background[{indic_annee_courante['dept_vnf_crise_code']}]")
    ligne2[3].write(":red-background[départements en crise]")

    # ligne3
    diff_indic_mois = indic_annee_courante['dept_vnf_vg_code'] - indic_mois_prec['dept_vnf_vg_code']
    signe=_signe_devant(diff_indic_mois)
    if signe == '':
        ligne3[0].write( "nombre de départements identique par rapport au mois dernier")
    else:
        ligne3[0].write(f"# {signe}{abs(diff_indic_mois)}")
        ligne3[0].write("départements en arrêté par rapport au mois dernier")

    diff_indic_mois = indic_annee_courante['dept_vnf_a_code'] - indic_mois_prec['dept_vnf_a_code']
    signe=_signe_devant(diff_indic_mois)
    if signe == '':
        ligne3[1].write( "nombre de départements identique par rapport au mois dernier")
    else:
        ligne3[1].write(f"# {signe}{abs(diff_indic_mois)}")
        ligne3[1].write("départements en arrêté par rapport au mois dernier")

    diff_indic_mois = indic_annee_courante['dept_vnf_ar_code'] - indic_mois_prec['dept_vnf_ar_code']
    signe=_signe_devant(diff_indic_mois)
    if signe == '':
        ligne3[2].write( "nombre de départements identique par rapport au mois dernier")
    else:
        ligne3[2].write(f"# {signe}{abs(diff_indic_mois)}")
        ligne3[2].write("départements en arrêté par rapport au mois dernier")

    diff_indic_mois = indic_annee_courante['dept_vnf_crise_code'] - indic_mois_prec['dept_vnf_crise_code']
    signe=_signe_devant(diff_indic_mois)
    if signe == '':
        ligne3[3].write( "nombre de départements identique par rapport au mois dernier")
    else:
        ligne3[3].write(f"# {signe}{abs(diff_indic_mois)}")
        ligne3[3].write("départements en arrêté par rapport au mois dernier")

    # ligne4
    liste_dept = ''
    if indic_annee_courante['dept_vnf_a_code'] >0:
        liste_dept = f"{indic_annee_courante['dept_vnf_a_nom']}"
    ligne4[1].write(f"{liste_dept}")

    liste_dept = ''
    if indic_annee_courante['dept_vnf_ar_code'] >0:
        liste_dept = f"{indic_annee_courante['dept_vnf_ar_nom']}"
    ligne4[2].write(f"{liste_dept}")

    liste_dept = ''
    if indic_annee_courante['dept_vnf_crise_code'] >0:
        liste_dept = f"{indic_annee_courante['dept_vnf_crise_nom']}"
    ligne4[3].write(f":red-background[{liste_dept}]")

#-------------------------------------------------------------------------------

def change_etat(valeur):
    """Change l'état de l'application en fonction de la valeur fournie."""
    st.session_state.construire_carte = valeur

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------

def main():
    """Fonction principale
    """
    # titre de page
    st.set_page_config(layout='centered',
                       page_title="Zones d'arrêtés sécheresse en vigueur")
    st.title("Arrêtés sécheresse en vigueur")

    # description de la fonctionnalité de téléchargement de la carte des arrêtés
    st.sidebar.info("""
    # L'application fonctionne de deux manières :

    - visualisation de la carte des arrêtés en vigueur récupérés automatiquement.
    - visualisation de la carte téléchargée au préalable manuellement.

    Pour utiliser le deuxième mode de visualisation, télécharger un fichier de carte des arrêtés à partir du lien suivant :
    [Télécharger la carte des arrêtés en vigueur](https://www.data.gouv.fr/api/1/datasets/r/bfba7898-aed3-40ec-aa74-abb73b92a363)

    Penser ensuite à zipper le fichier avant de le charger dans l'appli avec le bouton ci-dessous.
    """)
    # bouton de sélection du fichier à télécharger sur sidebar
    uploaded_file = st.sidebar.file_uploader("Choisir un fichier de carte des arrêtés", type=["zip"])

    # bouton pour lancer le traitement des données chargées
    # initialisation
    if 'construire_carte' not in st.session_state:
        st.session_state.construire_carte = None
    st.sidebar.button("Afficher la carte", on_click=change_etat, args=[True])

    tab1,tab2 = st.tabs(["Carte des arrêtés", "Indicateurs des arrêtés"])
    data_load_state = st.text('Chargement des données...')

    # itinéraires COP
    fic_couche = os.path.join(Racine,"Export_Itineraire_COP.gpkg")
    itineraire = lire_geopandas(fic_couche)
    # départements réseau VNF
    fic_couche = os.path.join(Racine,"departements_itineraires.gpkg")
    dept_iti = lire_geopandas(fic_couche)
    # conversion du CRS en wgs 84
    itineraire = itineraire.to_crs("EPSG:4326")
    dept_iti   = dept_iti.to_crs("EPSG:4326")
    # zones des arrêtés
    zones_arretes = get_zones_secheresse(uploaded_file)
    # conversion dans le même CRS que l'itinéraire
    zones_arretes = zones_arretes.to_crs(itineraire.crs)

    # arrêtés archivés dans le temps
    try:
        df_arretes = get_arretes()
    except Exception as e:
        print(e)
        data_load_state.text('Echec du téléchargement des données des arrêtés')
        df_arretes = pd.DataFrame()

    data_load_state.text('Chargement des données...Terminé !')

    # construction de la table des indicateurs à afficher
    if not df_arretes.empty:
        table_indic = construire_table_indic(df_arretes, zones_arretes, dept_iti)

    if st.session_state.construire_carte:
        # création de la carte
        data_load_state.text('Construction carte...')
        carte = construire_carte(itineraire, zones_arretes, dept_iti, uploaded_file)
        data_load_state.text('Construction carte...Terminé !')

        # visualisation
        with tab1:
            data_load_state.text('Visualisation carte...')
            st_folium(carte,
                    returned_objects=[], # pour éviter les appels répétés à l'appli
                    height=700,
                    width=700,
                    )
            data_load_state.text('Visualisation carte...Terminé !')
        # insertion des indicateurs par département
        with tab2:
            if not df_arretes.empty:
                data_load_state.text('Visualisation indicateurs...')
                inserer_indic_dept(table_indic)
                data_load_state.text('')
            else:
                data_load_state.text('Echec du téléchargement des données des arrêtés')
        # fin
        st.session_state.construire_carte = False

#-------------------------------------------------------------------------------

if __name__ == '__main__':
    main()

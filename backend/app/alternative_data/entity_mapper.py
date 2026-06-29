import pandas as pd
THEME_MAPPING = {

    "defence":

        [

            "Data Patterns",

            "Astra Microwave"

        ],

    "ems":

        [

            "Dixon",

            "Kaynes"

        ]
}


def map_theme_to_stocks(theme):

    return THEME_MAPPING.get(

        theme,

        []

    )

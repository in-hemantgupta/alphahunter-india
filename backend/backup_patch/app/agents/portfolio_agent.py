def portfolio_action(validation_score):

    if validation_score > 80:

        increase_sector_weight(

            "Defense"
        )

    elif validation_score > 60:

        increase_sector_weight(

            "Manufacturing"
        )

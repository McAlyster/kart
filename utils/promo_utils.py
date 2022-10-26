def getPromoByName(promo_name="") :
    """ Return a promotion object from a promo name"""
    # First filter by lastname similarity
    guessPromo = Promotion.objects.annotate(
                                        similarity=TrigramSimilarity('name', promo_name)
                                   ).filter(
                                        similarity__gt=0.8
                                    ).order_by('-similarity')
    if guessPromo :
        return guessPromo[0]
    print("Promo non trouvée", promo_name)
    return None


def kart2csv(field="",model=""):
    """ Return the corresponding csv field name from Kart field name"""
    try :
        return csvkart_mapping[model][field]
    except :
        return field


def csv2kart(field="", model=""):
    """ Return the corresponding Kart field name from current csv field name"""
    if "" == model :
        for model in csvkart_mapping.keys() :
            for k, v in csvkart_mapping[model].items():
                if v == field : return k
    else :
        for k, v in csvkart_mapping[model].items():
            if v == field : return k
    return field

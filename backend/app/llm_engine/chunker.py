def chunk_text(

    text,

    size=2000
):

    return [

        text[i:i+size]

        for i in range(

            0,

            len(text),

            size
        )

    ]

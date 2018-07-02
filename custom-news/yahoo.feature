Feature: yahoo
    @override
    Scenario: click title [goto channel]
        Given screen is searchret
        And searched is true
        When click @item_title
        Then screen is yahoo_channel

    @override
    Scenario: click image [goto channel]
        Given screen is searchret
        And searched is true
        When click @item_image
        Then screen is yahoo_channel

    @override
    Scenario: click item [goto channel]
        Given screen is searchret
        And searched is true
        When click @item
        Then screen is yahoo_channel



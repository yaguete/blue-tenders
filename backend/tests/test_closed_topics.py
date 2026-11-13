from app.jobs.closed_topics import listed_when_closed
from app.sources.eu_ft import EuFtSource


def test_a_closed_topic_with_text_stays_searchable_and_an_empty_one_does_not():
    rich = EuFtSource().to_tender(
        {
            "metadata": {
                "identifier": ["HORIZON-CL5-2023-D3-02-10"],
                "title": ["Wave devices"],
                "type": ["1"],
                "descriptionByte": ["<p>Expected outcome: more energy.</p>"],
            }
        }
    )
    thin = EuFtSource().to_tender(
        {
            "metadata": {
                "identifier": ["HORIZON-CL5-2023-D3-02-15"],
                "title": ["Another topic"],
                "type": ["1"],
            }
        }
    )
    rich.listed = listed_when_closed(rich)
    thin.listed = listed_when_closed(thin)
    assert rich.searchable()
    assert not thin.searchable()

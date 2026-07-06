from datetime import timedelta

from reply_config import inbound_replies_collection
from services.reply_processor_service import ensure_indexes, utc_now

DUMMY_REPLIES = [
    {
        "from_name": "Sarah Khan",
        "from_email": "sarah@northpeak.io",
        "company": "NorthPeak",
        "subject": "Re: Partnership idea",
        "reply_text": "This looks relevant. I am open to a short discussion this week.",
    },
    {
        "from_name": "Adeel Tariq",
        "from_email": "adeel@buildsphere.com",
        "company": "BuildSphere",
        "subject": "Re: Growth idea",
        "reply_text": "Please book a quick call. I would like to understand this better.",
    },
    {
        "from_name": "Hina Malik",
        "from_email": "hina@brightlane.co",
        "company": "BrightLane",
        "subject": "Re: Outreach",
        "reply_text": "Yes, interested. A 30 minute meeting would be useful.",
    },
    {
        "from_name": "Omar Shah",
        "from_email": "omar@cloudsmiths.dev",
        "company": "CloudSmiths",
        "subject": "Re: Proposal",
        "reply_text": "We are already working with another provider, so we will pass.",
    },
    {
        "from_name": "Ayesha Noor",
        "from_email": "ayesha@talentgrid.com",
        "company": "TalentGrid",
        "subject": "Re: Lead generation",
        "reply_text": "Not interested at the moment. Please remove me from future outreach.",
    },
    {
        "from_name": "Bilal Ahmad",
        "from_email": "bilal@novadata.ai",
        "company": "NovaData",
        "subject": "Re: Introduction",
        "reply_text": "Can you send more details about how this works?",
    },
    {
        "from_name": "Maria Joseph",
        "from_email": "maria@retailaxis.com",
        "company": "RetailAxis",
        "subject": "Re: Opportunity",
        "reply_text": "This may be useful, but please check back next quarter.",
    },
    {
        "from_name": "Hamza Ali",
        "from_email": "hamza@orbitworks.io",
        "company": "OrbitWorks",
        "subject": "Re: Meeting",
        "reply_text": "I am interested. Please set up a meeting and share the details.",
    },
    {
        "from_name": "Zara Sheikh",
        "from_email": "zara@launchforge.co",
        "company": "LaunchForge",
        "subject": "Re: Service",
        "reply_text": "No thanks. This is not a priority for our team.",
    },
    {
        "from_name": "Usman Raza",
        "from_email": "usman@marketpilot.io",
        "company": "MarketPilot",
        "subject": "Re: Follow up",
        "reply_text": "Could be relevant. What is the pricing model?",
    },
    {
        "from_name": "Nadia Imran",
        "from_email": "nadia@elevatehq.com",
        "company": "ElevateHQ",
        "subject": "Re: Discussion",
        "reply_text": "Happy to have a conversation. Please arrange a suitable slot.",
    },
    {
        "from_name": "Saad Ahmed",
        "from_email": "saad@vertexconsulting.com",
        "company": "Vertex Consulting",
        "subject": "Re: Offer",
        "reply_text": "We do not need this right now.",
    },
    {
        "from_name": "Mahnoor Iqbal",
        "from_email": "mahnoor@scalegrid.io",
        "company": "ScaleGrid",
        "subject": "Re: Collaboration",
        "reply_text": "Please contact our marketing lead instead.",
    },
    {
        "from_name": "Faraz Khan",
        "from_email": "faraz@signalcrest.com",
        "company": "SignalCrest",
        "subject": "Re: Introduction",
        "reply_text": "Yes, this is worth discussing. Please schedule a call.",
    },
    {
        "from_name": "Iqra Saeed",
        "from_email": "iqra@horizonlabs.io",
        "company": "Horizon Labs",
        "subject": "Re: Service",
        "reply_text": "We have no budget allocated for this, so not interested.",
    },
    {
        "from_name": "Danish Ali",
        "from_email": "danish@fusepoint.dev",
        "company": "FusePoint",
        "subject": "Re: Details",
        "reply_text": "Can you share a case study first?",
    },
    {
        "from_name": "Sana Qureshi",
        "from_email": "sana@blueorbit.co",
        "company": "BlueOrbit",
        "subject": "Re: Meeting request",
        "reply_text": "I would be interested in a quick meeting. Please send the meeting information.",
    },
    {
        "from_name": "Rafay Siddiqui",
        "from_email": "rafay@proxima.com",
        "company": "Proxima",
        "subject": "Re: Opportunity",
        "reply_text": "This is not relevant to our current plans.",
    },
    {
        "from_name": "Mehwish Tariq",
        "from_email": "mehwish@growthmint.io",
        "company": "GrowthMint",
        "subject": "Re: Proposal",
        "reply_text": "Possibly. I need to review this internally before deciding.",
    },
    {
        "from_name": "Tariq Hussain",
        "from_email": "tariq@bridgeworks.io",
        "company": "BridgeWorks",
        "subject": "Re: Call",
        "reply_text": "Interested. Please arrange the first available 30 minute slot.",
    },
]


def seed_dummy_replies() -> dict[str, int]:
    ensure_indexes()
    now = utc_now()
    inserted = 0
    already_exists = 0

    for index, reply in enumerate(DUMMY_REPLIES, start=1):
        document = {
            "reply_id": f"dummy_reply_{index:02d}",
            "main_company_id": "demo_ojiiz",
            "generated_email_id": "",
            "from_name": reply["from_name"],
            "from_email": reply["from_email"],
            "company": reply["company"],
            "subject": reply["subject"],
            "reply_text": reply["reply_text"],
            "received_at": now - timedelta(minutes=index),
            "tags": [],
            "classification": None,
            "meeting": None,
            "meeting_status": "",
            "processing_status": "pending",
            "processing_started_at": None,
            "processed_at": None,
            "created_at": now,
            "last_error": "",
        }

        result = inbound_replies_collection.update_one(
            {"reply_id": document["reply_id"]},
            {"$setOnInsert": document},
            upsert=True,
        )

        if result.upserted_id is not None:
            inserted += 1
        else:
            already_exists += 1

    return {
        "inserted": inserted,
        "already_exists": already_exists,
        "total_dummy_replies": len(DUMMY_REPLIES),
    }


if __name__ == "__main__":
    print(seed_dummy_replies())

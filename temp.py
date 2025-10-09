from rag_pipeline import generate_itinerary

query = "3-day trip to Taipei with night markets and temples"
itinerary = generate_itinerary(query)
print(itinerary)

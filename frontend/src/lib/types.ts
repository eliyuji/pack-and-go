export type FoodOption = {
  name?: string;
  district?: string;
  rating?: number;
  address?: string;
  lat?: number;
  lon?: number;
  place_id?: string;
  maps_url?: string;
  kind?: "stop" | "food";
};

export type Activity = {
  time?: string;
  activity?: string;
  food?: string;
  food_options?: FoodOption[];
  place?: FoodOption & { category?: string };
};

export type DayPlan = {
  day?: number;
  activities?: Activity[];
};

export type StructuredItinerary = {
  itinerary?: DayPlan[];
  sources?: string[];
};

export type TripResponse = {
  itinerary?: string;
  structured?: StructuredItinerary;
  modification?: {
    type?: string;
    target_day?: number;
    target_time?: string;
  };
  error?: string;
  detail?: string;
  sources?: string[];
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type SavedTrip = {
  id: string;
  query: string;
  structured: StructuredItinerary;
  formatted: string;
  savedAt: string;
};

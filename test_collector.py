import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from collect_water_data import collect_water_infrastructure_data

class TestWaterDataCollector(unittest.TestCase):

    @patch('googlemaps.Client')
    def test_collect_water_infrastructure_data(self, mock_gmaps_client):
        # Setup mock responses
        mock_instance = mock_gmaps_client.return_value
        mock_instance.places.side_effect = [
            {
                'results': [
                    {
                        'name': 'Sorek Desalination Plant',
                        'formatted_address': 'Sorek, Israel',
                        'geometry': {'location': {'lat': 31.9, 'lng': 34.7}},
                        'place_id': 'place_123',
                        'types': ['establishment', 'point_of_interest'],
                        'rating': 4.5,
                        'user_ratings_total': 100
                    }
                ],
                'next_page_token': None
            },
            {
                'results': [
                    {
                        'name': 'Eshkol Water Treatment Plant',
                        'formatted_address': 'Eshkol, Israel',
                        'geometry': {'location': {'lat': 32.8, 'lng': 35.3}},
                        'place_id': 'place_456',
                        'types': ['establishment'],
                        'rating': 4.2,
                        'user_ratings_total': 50
                    }
                ],
                'next_page_token': None
            }
        ]

        # Test queries
        queries = ["desalination Israel", "treatment Israel"]
        api_key = "fake_key"

        df = collect_water_infrastructure_data(api_key, queries)

        self.assertIsNotNone(df)
        self.assertEqual(len(df), 2)
        self.assertIn('Sorek Desalination Plant', df['name'].values)
        self.assertIn('Eshkol Water Treatment Plant', df['name'].values)
        self.assertEqual(df.iloc[0]['place_id'], 'place_123')

if __name__ == '__main__':
    unittest.main()

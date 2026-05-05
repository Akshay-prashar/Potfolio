"""Simple test runner for live inference."""

from inference import predict_live


def main() -> None:
    """Run a sample inference call and print readable output."""
    try:
        result = predict_live(
            batting_team="Mumbai Indians",
            bowling_team="Chennai Super Kings",
            runs=85,
            wickets=3,
            overs=10.2,
        )

        predicted_winner = result.get("predicted_winner", "N/A")
        win_percentage = result.get("win_percentage", "N/A")
        predicted_score = result.get("predicted_score")
        target_over = result.get("target_over", 20)

        print("Live Prediction Result")
        print("----------------------")
        print(f"Predicted Winner: {predicted_winner} ({win_percentage})")
        if predicted_score is None:
            print("Predicted Score: N/A")
        else:
            print(f"Predicted Score ({target_over} overs): {int(predicted_score)}")

    except Exception as exc:  # pylint: disable=broad-except
        print("Inference failed.")
        print(f"Error: {exc}")


if __name__ == "__main__":
    main()

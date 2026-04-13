from dataclasses import dataclass


@dataclass
class InverterData:
    current_power: str
    today_energy: str
    total_energy: str
    monthly_energy: str

    @classmethod
    def from_api_response(cls, plant_data: dict, device_power: str) -> "InverterData":
        return cls(
            current_power=device_power + "W",
            today_energy=plant_data.get("todayEnergy", "N/A"),
            total_energy=plant_data.get("totalEnergy", "N/A"),
            monthly_energy=plant_data.get("monthlyEnergy", "N/A"),
        )

    def to_display_dict(self) -> dict[str, str]:
        return {
            "Current Power": self.current_power,
            "Today Energy": self.today_energy,
            "Total Energy": self.total_energy,
            "Monthly Energy": self.monthly_energy,
        }

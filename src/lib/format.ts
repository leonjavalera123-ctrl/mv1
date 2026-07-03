// Small formatting helpers shared by components. All of this runs at build
// time — none of it ships to the browser.

// Circuit country -> FIA-style 3-letter badge. Flag emoji are unreliable
// (Chromium on Windows renders them as plain letters), so entry-list style
// country codes are both more robust and more "motorsport".
const COUNTRY_CODES: Record<string, string> = {
  Australia: 'AUS',
  Austria: 'AUT',
  Azerbaijan: 'AZE',
  Bahrain: 'BRN',
  Belgium: 'BEL',
  Brazil: 'BRA',
  Canada: 'CAN',
  China: 'CHN',
  France: 'FRA',
  Germany: 'GER',
  Hungary: 'HUN',
  Italy: 'ITA',
  Japan: 'JPN',
  Korea: 'KOR',
  Malaysia: 'MAS',
  Mexico: 'MEX',
  Monaco: 'MON',
  Netherlands: 'NED',
  Portugal: 'POR',
  Qatar: 'QAT',
  Russia: 'RUS',
  'Saudi Arabia': 'KSA',
  Singapore: 'SIN',
  Spain: 'ESP',
  Turkey: 'TUR',
  UAE: 'UAE',
  UK: 'GBR',
  USA: 'USA',
  'United States': 'USA',
  Vietnam: 'VIE',
};

export function countryCode(country: string): string {
  return COUNTRY_CODES[country] ?? country.slice(0, 3).toUpperCase();
}

export function shortDate(isoDate: string): string {
  return new Date(`${isoDate}T12:00:00Z`).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  });
}

// One-word result label for a race card corner.
export function resultLabel(race: {
  upcoming: boolean;
  finish: number | null;
  positionText: string | null;
}): string {
  if (race.upcoming) return 'Soon';
  if (race.finish !== null) return `P${race.finish}`;
  return 'DNF';
}

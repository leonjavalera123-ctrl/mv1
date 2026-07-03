// Build-time computation of the Records Wall. Everything numeric here is
// DERIVED from data/seasons/*.json — when a record falls, the wall updates
// on the next data refresh with zero code changes. Only records that can't
// be derived from our race data (age-based ones) are stated as facts.
import driver from '../../data/driver.json';

const seasonModules = import.meta.glob('../../data/seasons/*.json', {
  eager: true,
  import: 'default',
});
const seasons: any[] = Object.values(seasonModules).sort(
  (a: any, b: any) => a.season - b.season
);

function maxBySeason(pick: (summary: any) => number) {
  let best = { value: 0, season: 0 };
  for (const s of seasons) {
    const value = pick(s.summary);
    if (value > best.value) best = { value, season: s.season };
  }
  return best;
}

// Longest win streak across all races in chronological order (streaks can
// span a season boundary, so this walks the full career).
function longestWinStreak() {
  let streak = 0;
  let best = { length: 0, endSeason: 0 };
  for (const s of seasons) {
    for (const race of s.races) {
      if (race.upcoming) continue;
      streak = race.win ? streak + 1 : 0;
      if (streak > best.length) best = { length: streak, endSeason: s.season };
    }
  }
  return best;
}

// Longest run of consecutive championship seasons.
function consecutiveTitles() {
  const years: number[] = driver.career.championshipSeasons;
  let run = 0;
  let best = 0;
  for (let i = 0; i < years.length; i++) {
    run = i > 0 && years[i] === years[i - 1] + 1 ? run + 1 : 1;
    best = Math.max(best, run);
  }
  return { count: best, span: years.length ? `${years[0]}–${years[years.length - 1]}` : '' };
}

const wins = maxBySeason((s) => s.wins);
const points = maxBySeason((s) => s.championshipPoints);
const poles = maxBySeason((s) => s.poles);
const podiums = maxBySeason((s) => s.podiums);
const streak = longestWinStreak();
const titles = consecutiveTitles();

export interface RecordEntry {
  value: number | string;
  label: string;
  context: string;
}

export const records: RecordEntry[] = [
  {
    value: wins.value,
    label: 'Wins in a single season',
    context: `${wins.season} · an all-time F1 record`,
  },
  {
    value: streak.length,
    label: 'Consecutive race wins',
    context: `${streak.endSeason} · an all-time F1 record`,
  },
  {
    value: points.value,
    label: 'Points in a single season',
    context: `${points.season} · an all-time F1 record`,
  },
  {
    value: podiums.value,
    label: 'Podiums in a single season',
    context: `${podiums.season} · an all-time F1 record`,
  },
  {
    value: poles.value,
    label: 'Poles in a single season',
    context: `${poles.season}`,
  },
  {
    value: titles.count,
    label: 'Consecutive world titles',
    context: titles.span,
  },
  {
    value: '17y 166d',
    label: 'Youngest ever F1 starter',
    context: 'Australia 2015 · unbreakable — the rules were changed',
  },
  {
    value: '18y 228d',
    label: 'Youngest ever race winner',
    context: 'Spain 2016 · unbreakable',
  },
];

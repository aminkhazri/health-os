/**
 * Health OS — stretching routines and demo videos.
 * Everything here is plain data, so changing a routine or swapping a video is a one-line edit.
 */

// Each stretch: a one-line cue shown on the guided screen.
const STRETCHES = {
  'Cat-cow': 'On hands and knees. Round your back up, then let it sink. Slow, with your breath.',
  "Child's pose": 'Knees wide, sit back on your heels, arms long in front. Let your forehead rest.',
  "World's greatest stretch": 'Long lunge, both hands inside the front foot. Reach the inside arm to the ceiling and look at it.',
  'Downward dog': 'Hands and feet on the floor, hips high. Bend your knees as much as you need; press the floor away.',
  'Thread the needle': 'On hands and knees. Slide one arm under the other until the shoulder rests down. Breathe into your upper back.',
  'Half-kneeling hip flexor stretch': 'One knee down, other foot forward. Squeeze the glute of the down leg and shift forward. Stay tall.',
  'Lying hamstring stretch': 'On your back. Hold behind one thigh and straighten that knee until you feel the back of the leg.',
  'Figure-four stretch': 'On your back. Cross one ankle over the other knee and pull both legs toward your chest.',
  'Standing calf stretch': 'Hands on a wall, one leg back with the heel down and knee straight. Lean in.',
  'Butterfly stretch': 'Sit tall, soles of the feet together. Let the knees fall open; hinge forward a little from the hips.',
  'Doorway chest stretch': 'Forearm on a door frame, elbow at shoulder height. Step through until the chest opens.',
  'Supine spinal twist': 'On your back. Drop one knee across your body, arms wide, both shoulders heavy on the floor.',
};

// Each step: [stretch, seconds, eachSide]. eachSide = the timer runs once for the left and once for the right.
const STRETCH_ROUTINES = [
  { id: 'wake', icon: '🌅', name: 'Wake-up', when: 'Mornings, after you weigh in', steps: [
    ['Cat-cow', 60, false], ["Child's pose", 45, false], ["World's greatest stretch", 40, true],
    ['Downward dog', 45, false], ['Thread the needle', 35, true]] },
  { id: 'legs', icon: '⚽', name: 'Legs + hips', when: 'After a workout, or any time your legs feel tight', steps: [
    ['Half-kneeling hip flexor stretch', 40, true], ['Lying hamstring stretch', 40, true], ['Figure-four stretch', 40, true],
    ['Standing calf stretch', 30, true], ['Butterfly stretch', 60, false]] },
  { id: 'unwind', icon: '🌙', name: 'Unwind', when: 'After UPS, before bed', steps: [
    ["Child's pose", 60, false], ['Doorway chest stretch', 30, true], ['Supine spinal twist', 45, true],
    ['Figure-four stretch', 30, true], ['Cat-cow', 30, false]] },
];

/** Pure: total seconds in a routine (a step done on each side counts twice). */
function routineSeconds_(routine) {
  return routine.steps.reduce((sum, s) => sum + s[1] * (s[2] ? 2 : 1), 0);
}

// Demo videos: exercise or stretch name -> YouTube video ID (the part after "watch?v=").
// These are other people's short how-to videos; the app only plays them from YouTube, it doesn't copy them.
// If one is ever removed, the app still offers "Search YouTube" for that move. To swap one, change its ID here.
const VIDEOS = {
  // Workout A
  'Goblet squat': 'gCESNsDsbqk', 'Dumbbell floor press': 'uUGDRwge4F8', 'One-arm dumbbell row': 'nehAvSrfUOg',
  'Dumbbell Romanian deadlift': 'hQgFixeXdZo', 'Dumbbell shoulder press': 'B-aVuyhvLHU', 'Band pull-apart': 'bYsgk9SrJ48',
  // Workout B
  'Bulgarian split squat': 'uODWo4YqbT8', 'Single-leg Romanian deadlift': 'X2BM5J3UkEo', 'Dumbbell hip thrust': '29OfN4ztW_g',
  'Heel-raised goblet squat': 'RUXLuZ_GLrE', 'Standing calf raise': 'eMTy3qylqnE', 'Dead bug': 'GbSC02oU3To',
  // Workout C
  'Push-up': 'lsRAK6cr5kY', 'Band row': 'LSkyinhmA8k', 'Incline dumbbell press': 'gl8H4QLXKTo',
  'Dumbbell lateral raise': 'kDqklk1ZESo', 'Dumbbell curl': 'cBSD6mQIPQk', 'Overhead triceps extension': '-Vyt2QdsR7E',
  // Stretches
  'Cat-cow': '1Y0YjXS9sKI', "Child's pose": 'LZgABs0IggM', "World's greatest stretch": '-CiWQ2IvY34',
  'Downward dog': 'sd-Fn6xpyeg', 'Thread the needle': '6roMIB2YV4Y', 'Half-kneeling hip flexor stretch': 'gqoPYLUgP48',
  'Lying hamstring stretch': '5P3E8Pec_L8', 'Figure-four stretch': '-g0nuyTHMrI', 'Standing calf stretch': 'mafo7o7OnFo',
  'Butterfly stretch': '4J7kbCmPScQ', 'Doorway chest stretch': 'CEQMx4zFwYs', 'Supine spinal twist': 'mNdJti7ZwKI',
};

if (typeof module !== 'undefined') module.exports = { STRETCHES, STRETCH_ROUTINES, VIDEOS, routineSeconds_ }; // Node tests only

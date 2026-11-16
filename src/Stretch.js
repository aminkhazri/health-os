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
  // Hip mobility project
  '90/90 hip switch': 'Sit with both knees bent at 90°, one in front, one to the side. Rotate both knees to the other side and back. Sit tall; use your hands behind you at first.',
  'Hip CARs': 'On hands and knees. Lift one knee out to the side and draw the biggest slow circle you can with it, keeping the rest of your body still.',
  'Pigeon pose': 'Front shin across the mat, back leg long. Square your hips and fold forward until you feel the outer hip. Pad under the hip if needed.',
  'Frog stretch': 'On hands and knees, slide your knees wide with feet out to the sides. Rock your hips slowly back toward your heels.',
  'Deep squat hold': 'Feet a bit wider than hips, sink as low as you can with heels down. Hold a door frame or a light dumbbell at your chest. Push knees out with your elbows.',
  'Cossack squat': 'Wide stance. Shift down into one leg, keeping the other straight with toes up, then switch sides slowly. Only go as deep as is comfortable.',
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
  // Project routine: shown under "Projects" in the Stretch tab. Counts toward the Flex bar like the others.
  { id: 'hips', icon: '🦋', name: 'Hip mobility', project: true, when: 'Daily for 4 weeks, then 4 times a week. Evenings or after workouts.',
    why: 'Tight hips limit squat depth, stride length and kicking range, and pull on the lower back. Daily practice loosens them faster than occasional long sessions.',
    steps: [['90/90 hip switch', 60, false], ['Hip CARs', 30, true], ['Half-kneeling hip flexor stretch', 45, true],
      ['Pigeon pose', 45, true], ['Frog stretch', 60, false], ['Deep squat hold', 60, false], ['Cossack squat', 60, false]] },
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
  'Goblet squat': 'gCESNsDsbqk', 'Dumbbell floor press': 'ijKVXhRDJ-U', 'One-arm dumbbell row': 'jyrudAO4Rxc',
  'Dumbbell Romanian deadlift': 'O2dUYS-YYus', 'Dumbbell shoulder press': '-aVIf0bgMEs', 'Band pull-apart': 'bYsgk9SrJ48',
  // Workout B
  'Bulgarian split squat': '1bYdM_jK8nE', 'Single-leg Romanian deadlift': 'X2BM5J3UkEo', 'Dumbbell hip thrust': 'c3K1Afir9kk',
  'Heel-raised goblet squat': 'RUXLuZ_GLrE', 'Standing calf raise': 'nkAh8pFrvEA', 'Dead bug': 'GbSC02oU3To',
  // Workout C
  'Push-up': 'QCEyV-spfn8', 'Band row': 'LSkyinhmA8k', 'Incline dumbbell press': 'gl8H4QLXKTo',
  'Dumbbell lateral raise': '-_XE4qbV7Yw', 'Dumbbell curl': 'pl3z_AihNzk', 'Overhead triceps extension': 'rFNQv9eae6I',
  // Stretches
  'Cat-cow': '1Y0YjXS9sKI', "Child's pose": 'LZgABs0IggM', "World's greatest stretch": '-CiWQ2IvY34',
  'Downward dog': 'sd-Fn6xpyeg', 'Thread the needle': '6roMIB2YV4Y', 'Half-kneeling hip flexor stretch': 'gqoPYLUgP48',
  'Lying hamstring stretch': '5P3E8Pec_L8', 'Figure-four stretch': '-g0nuyTHMrI', 'Standing calf stretch': 'mafo7o7OnFo',
  'Butterfly stretch': '4J7kbCmPScQ', 'Doorway chest stretch': 'CEQMx4zFwYs', 'Supine spinal twist': 'mNdJti7ZwKI',
  // Neck project
  'Supine chin tuck': '7OgvJ653oxE', 'Neck isometric hold': 'WnKcq1Uh8m4', 'Prone neck extension': 'QrYSctbYQfg',
  'Side-lying neck raise': 'duOfvQUQfWQ', 'Dumbbell shrug': 'x22AJbViigk',
  // Calves project
  'Single-leg deficit calf raise': 'gUEffJQ2IdU', 'Seated dumbbell calf raise': 'fFWpWJy8ybU', 'Tibialis raise': 'VzIcGAgBiaM',
  // Hip mobility project
  '90/90 hip switch': 'qq_Z7sAmVrA', 'Hip CARs': 'hRMrq6G81p8', 'Pigeon pose': 'lqCqETr7Q0g', 'Frog stretch': '1wpyPsr0Rx0',
  'Deep squat hold': 'IHApHfNA2Ag', 'Cossack squat': 'nLNqEQ4B6XI',
  // Isometric holds
  'Copenhagen plank': 'bU8aazv5voo', 'Side plank': 'iNbH7_edNI8', 'Split squat bottom hold': '9-E7YW2WAlM',
  'Single-leg glute bridge hold': 'mUEViZ1R7l4', 'Push-up bottom hold': 'mmTAFhFpdY8', "Dumbbell farmer's hold": 'BJByPr07bts',
  'Single-leg calf raise hold': '7Udb4E3Uks8',
};

// Moves whose video is a vertical 3D-animated short from the DEMIC channel (youtube.com/@officialdemic). The app shows these in a tall frame.
// DEMIC has no clip for the stretches, neck, band or mobility moves, so those keep their regular how-to videos.
const TALL_VIDEOS = ['One-arm dumbbell row', 'Dumbbell floor press', 'Dumbbell Romanian deadlift', 'Dumbbell shoulder press', 'Bulgarian split squat', 'Dumbbell hip thrust',
  'Standing calf raise', 'Push-up', 'Dumbbell lateral raise', 'Dumbbell curl', 'Overhead triceps extension', 'Dumbbell shrug'];

if (typeof module !== 'undefined') module.exports = { STRETCHES, STRETCH_ROUTINES, VIDEOS, TALL_VIDEOS, routineSeconds_ }; // Node tests only

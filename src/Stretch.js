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

// Demo videos: exercise or stretch name -> YouTube video ID (the part after "watch?v=" or "/shorts/").
// Every one is a portrait YouTube Short. Where the DEMIC channel (youtube.com/@officialdemic, 3D-animated form clips) covers a move, its clip is used:
// the dumbbell row, Romanian deadlift, shoulder press, Bulgarian and split squat, hip thrust, heel-raised squat, calf raise, push-up, lateral raise,
// curl, triceps extension and shrug. DEMIC has nothing for the stretches, neck work, band moves, planks or mobility drills, so those come from other channels.
// These are other people's videos; the app only plays them from YouTube, it doesn't copy them. To swap one, change its ID here.
const VIDEOS = {
  // Workout A
  'Goblet squat': 'lRYBbchqxtI', 'Dumbbell floor press': 'UBmpZ7l5Nlk', 'One-arm dumbbell row': 'jyrudAO4Rxc',
  'Dumbbell Romanian deadlift': 'O2dUYS-YYus', 'Dumbbell shoulder press': '-aVIf0bgMEs', 'Band pull-apart': 'SuvO4TBwSu4',
  // Workout B
  'Bulgarian split squat': '1bYdM_jK8nE', 'Single-leg Romanian deadlift': 'R_fJ6H3FlVw', 'Dumbbell hip thrust': 'c3K1Afir9kk',
  'Heel-raised goblet squat': '0xjQPTonAs0', 'Standing calf raise': 'nkAh8pFrvEA', 'Dead bug': 'DqLL45uk2Tk',
  // Workout C
  'Push-up': 'QCEyV-spfn8', 'Band row': 'bBpK36TAQww', 'Incline dumbbell press': '8fXfwG4ftaQ',
  'Dumbbell lateral raise': '-_XE4qbV7Yw', 'Dumbbell curl': 'pl3z_AihNzk', 'Overhead triceps extension': 'rFNQv9eae6I',
  // Stretches
  'Cat-cow': '2of247Kt0tU', "Child's pose": '0KCP6cIzWoc', "World's greatest stretch": '7XheaZERvBQ',
  'Downward dog': 'M-3LOTCxLLw', 'Thread the needle': 'h6_v-dZGLjY', 'Half-kneeling hip flexor stretch': 'k9kK6su9F1c',
  'Lying hamstring stretch': 'U3Y84oBe8fc', 'Figure-four stretch': 'ckHZyA99Das', 'Standing calf stretch': 'tUA4MO1kXV8',
  'Butterfly stretch': 'kSHtwLxEEHw', 'Doorway chest stretch': 'O8rJw_TmC1Y', 'Supine spinal twist': 'ElKoMMaTPCM',
  // Neck project
  'Supine chin tuck': 'SCR25jcSVnU', 'Neck isometric hold': '-6ImdM-JmUU', 'Prone neck extension': 'G46gkrfa0NU',
  'Side-lying neck raise': 'QzDNcfVBS3U', 'Dumbbell shrug': 'x22AJbViigk',
  // Calves project
  'Single-leg deficit calf raise': 'E1mG5L9rpFc', 'Seated dumbbell calf raise': 'ar8nav0jGoE', 'Tibialis raise': 'pQcvW08rnAk',
  // Hip mobility project
  '90/90 hip switch': 'GC7YJ217uoU', 'Hip CARs': '5hPHUGoVCI4', 'Pigeon pose': 'AI5A1PRYX7E', 'Frog stretch': 'orMZYFWo9P0',
  'Deep squat hold': 'poKi7JPfuxE', 'Cossack squat': 'MJvazUpmdZU',
  // Isometric holds
  'Copenhagen plank': 'IXjQrC45D7s', 'Side plank': 'BFOyHDlY2UE', 'Split squat bottom hold': '-RffMuhmYc4',
  'Single-leg glute bridge hold': 'n1IZ168x2Bw', 'Push-up bottom hold': 'QCEyV-spfn8', "Dumbbell farmer's hold": 'Ozp9nI_w4xo',
  'Single-leg calf raise hold': 'nkAh8pFrvEA',
};

if (typeof module !== 'undefined') module.exports = { STRETCHES, STRETCH_ROUTINES, VIDEOS, routineSeconds_ }; // Node tests only

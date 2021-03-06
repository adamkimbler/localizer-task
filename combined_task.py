"""
Slow event-related design for HRF estimation for M1, V1, and A1.

Single-run task that includes the following conditions:
- flashing checkerboard
- finger tapping
- listening to tones/music

Originally created by Jakub Kaczmarzyk and adapted to combine tasks.
"""

from __future__ import division, print_function
import time
import os
import os.path as op
from datetime import datetime
import numpy as np
import pandas as pd
import psychopy  # pylint: disable=E0401
import psychopy.core  # pylint: disable=E0401
import psychopy.event  # pylint: disable=E0401
import psychopy.gui  # pylint: disable=E0401
import psychopy.visual  # pylint: disable=E0401
import psychopy.sound  # pylint: disable=E0401
from psychopy.constants import STARTED, STOPPED  # pylint: disable=E0401
psychopy.prefs.general['audioLib'] = ['sounddevice', 'pygame']
# psychopy.prefs.general['audioDevice'] = ['Built-in Output']

_TAPPING_INSTRUCTIONS = 'Tap your fingers as quickly as possible!'

# These tracks are 20 seconds long.
# 10s versions created by
# https://www.audiocheck.net/audiofrequencysignalgenerator_sinetone.php
# Durations doubled with Audacity.
_TONE_FILES = ['audio/250Hz_20s.wav',
               'audio/500Hz_20s.wav',
               'audio/600Hz_20s.wav',
               'audio/750Hz_20s.wav',
               'audio/850Hz_20s.wav']
TRIAL_DICT = {1: 'Checkerboard', 2: 'Tone', 3: 'Tapping'}
N_CONDS = len(TRIAL_DICT.keys())  # audio, checkerboard, tapping
N_BLOCKS = 3  # for detection task
N_TRIALS = 14  # for each condition
DUR_RANGE = (1, 5)  # avg of 3s
ITI_RANGE = (3, 11.84)  # max determined to minimize difference from TASK_TIME
TASK_TIME = 438  # time for trials in task
START_DUR = 6  # fixation before trials
END_DUR = 6  # fixation after trials
# total time = TASK_TIME + START_DUR + END_DUR = 450 = 7.5 mins


def close_on_esc(win):
    """
    Closes window if escape is pressed
    """
    if 'escape' in psychopy.event.getKeys():
        win.close()
        psychopy.core.quit()


def flash_stimuli(win, stimuli, duration, frequency=1):
    """
    Flash stimuli.

    Parameters
    ----------
    win : (psychopy.visual.Window) window in which to draw stimuli
    stimuli : (iterable) some iterable of objects with `.draw()` method
    duration : (numeric) duration of flashing in seconds
    frequency : (numeric) frequency of flashing in Hertz
    """
    start_time = time.time()
    duration_one_display = 1 / frequency
    n_stim = len(stimuli)
    counter = 0
    response = psychopy.event.BuilderKeyResponse()
    response.tStart = start_time
    response.frameNStart = 0
    response.status = STARTED
    window.callOnFlip(response.clock.reset)
    psychopy.event.clearEvents(eventType='keyboard')
    while time.time() - start_time < duration:
        keys = psychopy.event.getKeys(keyList=['1', '2'],
                                      timeStamped=trials_clock)
        if keys:
            response.keys.extend(keys)
            response.rt.append(response.clock.getTime())
        _this_start = time.time()
        while time.time() - _this_start < duration_one_display:
            this_stim = stimuli[counter % n_stim]
            win.flip()
            keys = psychopy.event.getKeys(keyList=['1', '2'],
                                          timeStamped=trials_clock)
            if keys:
                response.keys.extend(keys)
                response.rt.append(response.clock.getTime())
            this_stim.draw()

            close_on_esc(win)
        counter += 1
    response.status = STOPPED
    return response.keys, response.rt


def draw(win, stim, duration):
    """
    Draw stimulus for a given duration.

    Parameters
    ----------
    win : (psychopy.visual.Window)
    stim : object with `.draw()` method
    duration : (numeric) duration in seconds to display the stimulus
    """
    # Use a busy loop instead of sleeping so we can exit early if need be.
    start_time = time.time()
    response = psychopy.event.BuilderKeyResponse()
    response.tStart = start_time
    response.frameNStart = 0
    response.status = STARTED
    window.callOnFlip(response.clock.reset)
    psychopy.event.clearEvents(eventType='keyboard')
    while time.time() - start_time < duration:
        stim.draw()
        keys = psychopy.event.getKeys(keyList=['1', '2'],
                                      timeStamped=trials_clock)
        if keys:
            response.keys.extend(keys)
            response.rt.append(response.clock.getTime())
        close_on_esc(win)
        win.flip()
    response.status = STOPPED
    return response.keys, response.rt


class Checkerboard(object):
    """
    Create an instance of a `Checkerboard` object.

    Parameters
    ----------
    win : (psychopy.visual.Window) window in which to display stimulus
    side_len : (int) number of rings in radial checkerboard
    inverted : (bool) if true, invert black and white squares
    size : (numeric) size of checkerboard
    kwds : keyword arguments to psychopy.visual.ImageStim
    """

    def __init__(self, win, side_len=8, inverted=False, size=16, **kwds):
        self.win = win
        self.side_len = side_len
        self.inverted = inverted
        self.size = size

        self._array = self._get_array()
        self._stim = psychopy.visual.RadialStim(
            win=self.win, tex=self._array, size=self.size, radialCycles=1,
            **kwds
        )

    def _get_array(self):
        """Return square `np.ndarray` of alternating ones and negative ones
        with shape `(self.side_len, self.side_len)`."""
        board = np.ones((self.side_len, self.side_len), dtype=np.int32)
        board[::2, ::2] = -1
        board[1::2, 1::2] = -1
        return board if not self.inverted else board * -1

    def draw(self):
        """Draw checkerboard object."""
        self._stim.draw()


def trial_duration_and_iti(dur_range, iti_range, n_trials, n_conds, seed=None):
    """
    Produces lists containing n_conds arrays of n_trials length for trial
    durations and intertrial intervals based on a uniform distribution.
    The process is iterative to minimize the amount of duration lost
    """
    length = (np.average(dur_range) + np.average(iti_range)) * n_trials
    print('Total desired time: {0}s'.format(TASK_TIME))
    print('Total requested time: {0}s'.format(length * n_conds))
    if np.abs((length * n_conds) - TASK_TIME) > 10:
        raise Exception('Inputs do not seem compatible with total desired '
                        'time.')
    missing_time_per_cond = np.finfo(dtype='float64').max
    if seed:
        seed *= 1000  # allows for space to change
    else:
        seed = np.random.randint(1000, 9999)

    while not np.isclose(missing_time_per_cond, 0.0, atol=.001):
        state = np.random.RandomState()
        trial_durs = state.uniform(dur_range[0], dur_range[1], n_trials)
        trial_itis = state.uniform(iti_range[0], iti_range[1], n_trials)
        missing_time_per_cond = length - np.sum(trial_durs + trial_itis)
        seed += 1

    # Fill in one trial's ITI with missing time for constant total time
    print('Current missing time: {0}s'.format(missing_time_per_cond))
    print('Discrepancy: {0}s'.format(TASK_TIME - (length * n_conds)))
    missing_time_per_cond += (TASK_TIME / n_conds) - length
    total_missing_time = missing_time_per_cond * n_conds
    print('Final missing time: {0}s'.format(total_missing_time))
    trial_itis[-1] += missing_time_per_cond

    all_cond_trial_durs = [np.random.permutation(trial_durs) for _ in range(n_conds)]
    all_cond_trial_itis = [np.random.permutation(trial_itis) for _ in range(n_conds)]
    print('Total time: {0}s'.format(np.sum(all_cond_trial_durs) +
                                    np.sum(all_cond_trial_itis)))
    return all_cond_trial_durs, all_cond_trial_itis


if __name__ == '__main__':
    # Collect user input
    # ------------------
    # Remember to turn fullscr to True for the real deal.

    exp_info = {'subject': '',
                'session': '',
                'ttype': ['Estimation', 'Detection']}
    dlg = psychopy.gui.DlgFromDict(
        exp_info,
        title='Primary {0}'.format(exp_info['ttype']),
        order=['subject', 'session'])
    window = psychopy.visual.Window(
        size=(800, 600), fullscr=True, monitor='testMonitor', units='deg',)
    if not dlg.OK:
        psychopy.core.quit()

    filename = ('data/sub-{0}_ses-{1}_task-primary{2}'
                '_run-01_events').format(exp_info['subject'],
                                         exp_info['session'],
                                         exp_info['ttype'])
    if op.exists(filename + '.tsv'):
        raise ValueError('Output file already exists.')

    # Initialize stimuli
    # ------------------
    print('Determining durations and ITIs')
    durs, itis = trial_duration_and_iti(
        dur_range=DUR_RANGE, iti_range=ITI_RANGE, n_trials=N_TRIALS,
        n_conds=N_CONDS)
    print('Done determination')
    # Checkerboards
    checkerboards = (Checkerboard(window), Checkerboard(window, inverted=True))
    # Tones
    tones = [psychopy.sound.Sound(tf) for tf in _TONE_FILES]
    tone_nums = np.arange(len(tones))
    tone_nums = np.repeat(tone_nums, 5)  # just assume 25 trials for now
    np.random.shuffle(tone_nums)  # pylint: disable=E1101
    tone = psychopy.visual.TextStim(window, '', height=2, wrapWidth=30)
    # Finger tapping instructions
    tapping = psychopy.visual.TextStim(window, _TAPPING_INSTRUCTIONS, height=2,
                                       wrapWidth=30)
    # Rest between tasks
    crosshair = psychopy.visual.TextStim(window, '+', height=2)
    # Waiting for scanner
    waiting = psychopy.visual.TextStim(window, "Waiting for scanner ...")

    # Scanner runtime
    # ---------------
    # Wait for trigger from scanner.
    waiting.draw()
    window.flip()
    psychopy.event.waitKeys(keyList=['space', '5'])

    startTime = datetime.now()
    routine_clock = psychopy.core.Clock()
    trials_clock = psychopy.core.Clock()
    COLUMNS = ['trial_number', 'onset', 'duration', 'trial_type',
               'response_time', 'tap_count', 'tap_duration', 'stim_file']
    data_set = {c: [] for c in COLUMNS}
    if not os.path.isdir('data'):
        os.makedirs('data')
    log_file = psychopy.logging.LogFile(filename + '.log',
                                        level=psychopy.logging.DATA)
    psychopy.logging.console.setLevel(psychopy.logging.DATA)

    # Start with six seconds of rest
    draw(win=window, stim=crosshair, duration=START_DUR)

    # set order of trials
    if exp_info['ttype'] == 'Estimation':
        # randomize order
        trials = list(range(1, N_CONDS + 1))
        trials *= N_TRIALS
        np.random.shuffle(trials)  # pylint: disable=E1101
    elif exp_info['ttype'] == 'Detection':
        N_TRIALS_PER_BLOCK = np.ceil(N_TRIALS // N_BLOCKS)
        BLOCK_LIST = []
        chop_flag = True
        chop_num = N_TRIALS
        while chop_flag:
            BLOCK_LIST.append(N_TRIALS_PER_BLOCK)
            chop_num -= N_TRIALS_PER_BLOCK
            if chop_num < N_TRIALS_PER_BLOCK:
                BLOCK_LIST.append(chop_num)
                chop_flag = False
        # shuffle order of conditions (but repeated in same order across blocks)
        cond_list = list(range(1, N_CONDS + 1))
        np.random.shuffle(BLOCK_LIST)
        np.random.shuffle(cond_list)
        print(BLOCK_LIST, cond_list)
        trials = [[[x] * y for x in cond_list] for y in BLOCK_LIST]
        trials = [item for sublist in trials for item in sublist]
        trials = [item for sublist in trials for item in sublist]

    c = 0  # tone trial counter
    trial_type_num = {1: 0, 2: 0, 3: 0}  # trial type counter
    for trial_num, trial_type in enumerate(trials):
        trials_clock.reset()
        data_set['trial_number'].append(trial_num + 1)
        data_set['onset'].append(routine_clock.getTime())
        data_set['trial_type'].append(TRIAL_DICT[trial_type])
        task_keys = []
        rest_keys = []
        trial_duration = durs[trial_type - 1][trial_type_num[trial_type]]
        rest_duration = itis[trial_type - 1][trial_type_num[trial_type]]
        trial_type_num[trial_type] += 1
        if trial_type == 1:
            # flashing checkerboard
            task_keys, _ = flash_stimuli(window, checkerboards,
                                         duration=trial_duration, frequency=5)
            data_set['stim_file'].append('n/a')
        elif trial_type == 2:
            # tone
            tone_num = tone_nums[c]
            tones[tone_num].play()
            task_keys, _ = draw(win=window, stim=crosshair, duration=trial_duration)
            tones[tone_num].stop()
            c += 1
            data_set['stim_file'].append(_TONE_FILES[tone_num])
        elif trial_type == 3:
            # finger tapping
            task_keys, _ = draw(win=window, stim=tapping, duration=trial_duration)
            data_set['stim_file'].append('n/a')
        else:
            raise Exception()

        # Rest
        rest_keys, _ = draw(win=window, stim=crosshair, duration=rest_duration)
        if task_keys and rest_keys:
            data_set['tap_duration'].append((trial_duration + rest_keys[-1][1]) - task_keys[0][1])
            data_set['response_time'].append(task_keys[0][1])
        elif task_keys and not rest_keys:
            data_set['response_time'].append(task_keys[0][1])
            data_set['tap_duration'].append(task_keys[-1][1] - task_keys[0][1])
        elif rest_keys and not task_keys:
            data_set['response_time'].append(trial_duration + rest_keys[0][1])
            data_set['tap_duration'].append(rest_keys[-1][1] - rest_keys[0][1])
        else:
            data_set['response_time'].append(np.nan)
            data_set['tap_duration'].append(np.nan)
        data_set['tap_count'].append((len(task_keys) + len(rest_keys)))
        data_set['duration'].append(routine_clock.getTime() - data_set['onset'][-1])
        psychopy.logging.flush()

    # End with six seconds of rest
    draw(win=window, stim=crosshair, duration=END_DUR)

    # finish running trials
    out_frame = pd.DataFrame(data_set, columns=COLUMNS)
    out_frame.to_csv(filename + '.tsv', sep='\t', na_rep='n/a', index=False)

    end_screen = psychopy.visual.TextStim(window, "The task is now complete!")
    end_screen.draw()
    window.flip()
    psychopy.event.waitKeys(keyList=['space', '5', 'escape'])

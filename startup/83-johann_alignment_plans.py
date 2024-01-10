import pandas as pd
from xas.spectrometer import analyze_elastic_fly_scan, analyze_linewidth_fly_scan, get_optimal_crystal_alignment_position
from xas.process import get_processed_df_from_uid_for_epics_fly_scan


ALIGNMENT_SAMPLE_NAME = 'alignment sample'
ALIGNMENT_SAMPLE_UID = 'alignment'

def step_scan_simple_johann_piezo_plan(crystal=None, axis=None, scan_range=None, step_size=None, exposure_time=0.5, plot_func=None, liveplot_kwargs=None, md=None):
    motor_description = _crystal_alignment_dict[crystal][axis]
    rel_start, rel_stop, num_steps = convert_range_to_start_stop(scan_range, step_size)
    yield from general_scan(detectors=['Pilatus 100k'], motor=motor_description, rel_start=rel_start, rel_stop=rel_stop,
                            num_steps=num_steps, exposure_time=exposure_time, liveplot_kwargs={}, md=md)

def fly_epics_scan_simple_johann_piezo_plan(crystal=None, axis=None, scan_range=None, duration=None, plot_func=None, liveplot_kwargs=None, md=None):
    crystals = [crystal]
    detectors = [pil100k_stream]
    relative_trajectory = {'positions': [-scan_range/2, scan_range/2],
                           'durations': [duration]}
    if md is None: md = {}
    yield from epics_fly_scan_custom_johann_piezo_plan(crystals=crystals, axis=axis, detectors=detectors,
                                                       relative_trajectory=relative_trajectory, md=md)


#
# plan = epics_fly_scan_custom_johann_piezo_plan(#crystals=['main', 'aux4', 'aux2'],
#                                                crystals=['main', 'aux2', 'aux3', 'aux4', 'aux5'],
#                                                 axis='roll',
#                                                 detectors=[pil100k_stream, apb_stream],
#                                                 relative_trajectory={'positions': [-400, -395, 395, 400],
#                                                                      'durations': [0.1, 30, 0.1]},
#                                                 md={'experiment': 'epics_fly_scan'})
# RE(plan)

def simple_johann_piezo_plan(scan_kind=None, **kwargs):
    if scan_kind == 'step':
        yield from step_scan_simple_johann_piezo_plan(**kwargs)
    elif scan_kind == 'fly':
        yield from fly_epics_scan_simple_johann_piezo_plan(**kwargs)

def tune_johann_piezo_plan(property='com', pil100k_roi_num=None, scan_kind=None, **kwargs):
    yield from simple_johann_piezo_plan(scan_kind, **kwargs)
    if scan_kind == 'step':
        t = db[-1].table()
        y = t[f'pil100k_stats{pil100k_roi_num}_total'].values
    elif scan_kind == 'fly':
        t = get_processed_df_from_uid_for_epics_fly_scan(db, -1)
        y = t[f'pil100k_roi{pil100k_roi_num}'].values

    motor_description = _crystal_alignment_dict[kwargs['crystal']][kwargs['axis']]
    motor_object = get_motor_device(motor_description, based_on='description')
    x = t[motor_object.name].values

    if property == 'com':
        # new_position = np.sum((y - y.min()) * x) / np.sum((y - y.min()))
        _y = y - y.min()
        _y_half = _y >= np.percentile(_y, 50)
        new_position = np.sum((_y * x)[_y_half]) / np.sum(_y[_y_half])
    elif property == 'max':
        new_position = x[np.argmax(y)]
    else:
        raise ValueError('not implemented')
    print_to_gui(f'Moving motor {motor_description} to position {new_position}', tag='spectrometer', add_timestamp=True)
    yield from move_motor_plan(motor_attr=motor_description, based_on='description', position=new_position)

# RE(tune_johann_piezo_plan(pil100k_roi_num=1, scan_kind='fly', crystal='aux5', axis='yaw', scan_range=1000, duration=10, md={}))
# RE(tune_johann_piezo_plan(pil100k_roi_num=1, scan_kind='fly', crystal='aux2', axis='yaw', scan_range=500, duration=5, md={}))

def johann_add_scan_to_alignment_data_plan(alignment_data=None, alignment_plan='', _uid=-1, rois=None):
    if alignment_data is not None:
        start = db[_uid].start
        uid = start.uid
        alignment_data.append({
            'crystal': start['alignment_crystal'],
            'tweak_motor_description': start['tweak_motor_description'],
            'tweak_motor_position': start['tweak_motor_position'],
            'scan_scope': start['scan_scope'],
            'alignment_plan': alignment_plan,
            'rois': rois,
            'uid': uid, })
    yield from bps.null()



# def _johann_analyze_alignment_data(alignment_data, scan_scope='alignment', force_analysis=False, plot_func=None):


def _johann_analyze_alignment_data_entry(entry):
    if entry['alignment_plan'] == 'fly_scan_johann_elastic_alignment_plan_bundle':
        fwhm_value, max_value, max_loc, com_loc = analyze_elastic_fly_scan(db, entry['uid'],
                                                                           rois=entry['rois'])
    elif entry['alignment_plan'] == 'epics_fly_scan_johann_emission_alignment_plan_bundle':
        x_key = db[uid].start['motor_stream_names'][0].replace('_monitor', '')
        fwhm_value, max_value, max_loc, com_loc = analyze_linewidth_fly_scan(db, entry['uid'],
                                                                             x_key=x_key,
                                                                             rois=entry['rois'])
    # elif entry['alignment_plan'] == 'fly_scan_johann_herfd_alignment_plan_bundle':
    #     pass
    else:
        raise NotImplementedError('This is not yet implemented')
    entry['fwhm_value'] = fwhm_value
    entry['max_value'] = max_value
    entry['max_loc'] = max_loc
    entry['com_loc'] = com_loc

def johann_analyze_alignment_data_entry(entry, attempts=5, sleep=3):
    for i in range(attempts):
        try:
            _johann_analyze_alignment_data_entry(entry)
            break
        except Exception as e:
            ttime.sleep(sleep)

def johann_analyze_alignment_data_plan(alignment_data=None, scan_scope=None, alignment_plan=None, crystal=None, force_analysis=False, plot_func=None, ):
    if alignment_data is not None:
        for entry in alignment_data:
            if ((entry['scan_scope'] == scan_scope) and
                ((crystal is None) or (entry['crystal']==crystal)) and
                ((alignment_plan is None) or (entry['alignment_plan'] == alignment_plan))):
                if force_analysis or any(k not in entry.keys() for k in ['fwhm_value', 'max_value', 'max_loc', 'com_loc']):
                    johann_analyze_alignment_data_entry(entry)
    yield from bps.null()



# def johann_analyze_herfd_calibration_data_plan(calibration_data=None, liveplot_kwargs=None):
#     fom = _scan_fom_dict['herfd']['calibration']['fom']
#     polarity = _scan_fom_dict['herfd']['calibration']['polarity']
#     calibration_data = pd.DataFrame(calibration_data)
#     # do the analysis



def fly_scan_johann_elastic_alignment_plan_bundle(crystal=None, e_cen=8000.0, scan_range=10.0, duration=5.0, motor_info='', md=None):
    e_velocity = scan_range / duration
    trajectory_filename = scan_manager.quick_linear_trajectory_filename(e_cen, scan_range, e_velocity)
    if md is None: md = {}

    md = {'sample_name': ALIGNMENT_SAMPLE_NAME,
          'sample_uid': ALIGNMENT_SAMPLE_UID,
          'spectrometer_current_crystal': crystal,
          **md}

    name = f'{crystal} elastic scan at {e_cen: 0.1f} {motor_info}'
    scan_kwargs = {'name': name, 'comment': '',
                   'trajectory_filename': trajectory_filename,
                   'detectors': ['Pilatus 100k'],
                   'element': '', 'e0': e_cen, 'edge': '',
                   'metadata': md}
    return [{'plan_name': 'fly_scan_plan',
                  'plan_kwargs': {**scan_kwargs}}]

# plans = fly_scan_johann_elastic_alignment_plan_bundle(crystal='aux5', e_cen=8046, scan_range=12, duration=20, motor_info='Cu foil spot2', md={})
# plan_processor.add_plans(plans)

def epics_fly_scan_johann_emission_alignment_plan_bundle(crystal=None, mono_energy=None, scan_range=None, duration=None, motor_info='', md=None):
    if md is None: md = {}
    md = {'sample_name': ALIGNMENT_SAMPLE_NAME,
          'sample_uid': ALIGNMENT_SAMPLE_UID,
          'plan_name': 'epics_fly_scan_johann_emission_alignment_plan',
          **md}

    name = f'{crystal} emission scan at {motor_info}'
    scan_kwargs = {'name': name, 'comment': '', 'detectors': ['Pilatus 100k'],
                   'mono_energy': mono_energy,
                   'spectrometer_central_energy': None,
                   'relative_trajectory': {'positions' : [-scan_range/2, scan_range/2], 'durations': [duration]},
                   'crystal_selection': crystal,
                   'element': '', 'e0': None, 'line': '',
                   'metadata': md}

    return [{'plan_name': 'epics_fly_scan_johann_xes_plan',
             'plan_kwargs': scan_kwargs}]

# plans = epics_fly_scan_johann_emission_alignment_plan_bundle(crystal='aux2', mono_energy=11570, scan_range=1000, duration=10, motor_info='test', md={})
# plan_processor.add_plans(plans)


def fly_scan_johann_herfd_alignment_plan_bundle(crystal=None, element=None, edge=None, duration=None, scan_range=None, motor_info='', md=None):
    trajectory_filename = scan_manager.quick_herfd_trajectory_filename(element, edge, duration, scan_range)
    e0 = xraydb.xray_edge(element, edge).energy
    if md is None: md = {}

    md = {'sample_name': ALIGNMENT_SAMPLE_NAME,
          'sample_uid': ALIGNMENT_SAMPLE_UID,
          'spectrometer_current_crystal': crystal,
          **md}

    name = f'{crystal} herfd scan at {element}-{edge} {motor_info}'
    scan_kwargs = {'name': name, 'comment': '',
                   'trajectory_filename': trajectory_filename,
                   'detectors': ['Pilatus 100k'],
                   'element': element, 'e0': e0, 'edge': edge,
                   'metadata': md}
    return [{'plan_name': 'fly_scan_plan',
             'plan_kwargs': scan_kwargs}]

# plans = fly_scan_johann_herfd_alignment_plan_bundle(crystal='main', element='Cu', edge='K', duration=10, motor_info='test', md={})
# plan_processor.add_plans(plans*3)

def johann_alignment_scan_plan_bundle(alignment_plan=None, rois=None,  alignment_data=None,
                                      liveplot_kwargs=None, plan_gui_services=None, **scan_kwargs):
    plans = []
    plans.append({'plan_name': alignment_plan,
                  'plan_kwargs': {**scan_kwargs}})
    plans.append({'plan_name': 'johann_add_scan_to_alignment_data_plan',
                  'plan_kwargs': {'alignment_data': alignment_data,
                                  'alignment_plan': alignment_plan,
                                  '_uid': -1,
                                  'rois': rois}})
    return plans


def johann_focus_on_one_crystal_plan(crystal, yaw_shift=1200, print_msg=True):
    if print_msg:
        print_to_gui(f'Setting the focus on the {crystal} crystal. Moving other crystals from the field of view.',
                     add_timestamp=True, tag='Spectrometer')

    enabled_crystals = johann_emission.enabled_crystals_list
    unwanted_crystals = [c for c in enabled_crystals if c != crystal]
    for cr in unwanted_crystals:
        yaw_direction = 1 if cr in ['aux3', 'aux5'] else -1
        yield from move_relative_motor_plan(motor_attr=_crystal_alignment_dict[cr]['yaw'],
                                            based_on='description',
                                            rel_position=yaw_shift * yaw_direction)


def undo_johann_focus_on_one_crystal_plan(crystal, yaw_shift=1200):
    print_to_gui(f'Focus was on the {crystal} crystal. Moving other crystals back into the field of view.',
                 add_timestamp=True, tag='Spectrometer')
    yield from johann_focus_on_one_crystal_plan(crystal, yaw_shift=-yaw_shift, print_msg=False)


def get_johann_crystal_axis_motor_pos(crystal, axis):
    motor_description = _crystal_alignment_dict[crystal][axis]
    motor_obj = get_motor_device(motor_description, based_on='description')
    return motor_obj.position

def get_tweak_motor_positions_for_crystal(crystal, tweak_motor_axis, motor_range_mm, motor_num_steps):
    motor_description = _crystal_alignment_dict[crystal][tweak_motor_axis]
    motor_obj = get_motor_device(motor_description, based_on='description')
    motor_pos_init = motor_obj.position

    motor_pos_start = motor_pos_init - motor_range_mm / 2
    motor_pos_stop = motor_pos_init + motor_range_mm / 2

    motor_pos_steps = np.linspace(motor_pos_start, motor_pos_stop, motor_num_steps)

    motor_low_lim = motor_obj.low_limit # check this
    motor_high_lim = motor_obj.high_limit  # check this
    motor_pos_steps = motor_pos_steps[(motor_pos_steps >= motor_low_lim) & (motor_pos_steps <= motor_high_lim)]
    return motor_pos_init, motor_pos_steps, motor_description

def find_optimal_crystal_alignment_position(alignment_data=None, scan_scope=None, alignment_plan=None, crystal=None, fom=None, plot_func=None):
    multiplier = 1 if fom=='max_value' else -1
    key_checklist = [scan_scope, fom]
    if alignment_plan is not None: key_checklist.append(alignment_plan)
    if crystal is not None: key_checklist.append(crystal)
    description = [v['tweak_motor_description'] for v in alignment_data if all(k in v.keys() for k in key_checklist)][0]
    x = [v['tweak_motor_position'] for v in alignment_data if all(k in v.keys() for k in key_checklist)]
    y = [v[fom] * multiplier for v in alignment_data if all(k in v.keys() for k in key_checklist)]
    position = get_optimal_crystal_alignment_position(x, y, plot_func=plot_func)
    return position, description

def move_to_optimal_crystal_alignment_position_plan(**kwargs):
    position, tweak_motor_description = find_optimal_crystal_alignment_position(**kwargs)
    print_to_gui(f'Best position for {tweak_motor_description} was found to be {position}', add_timestamp=True, tag='Spectrometer')
    yield from move_motor_plan(motor_attr=tweak_motor_description, based_on='description', position=position)



_scan_fom_dict = {'emission': {'alignment':   {'fom': 'emission_line_fwhm', 'polarity': 'pos'}},
                  'elastic':  {'alignment':   {'fom': 'elastic_line_fwhm',  'polarity': 'pos'}},
                  'herfd':    {'alignment':   {'fom': 'herfd_fom', 'polarity': 'pos'},
                               'calibration': {'fom': 'chisq', 'polarity': 'pos'}}}


def move_rowland_circle_R_plan(new_R=None, energy=None, translations_only=True):
    motors_to_move = copy.deepcopy(johann_emission.real_keys)
    if translations_only:
        _motors_to_move = []
        for motor in motors_to_move:
            if not (motor.endswith('yaw') or motor.endswith('roll')):
                _motors_to_move.append(motor)
        motors_to_move = _motors_to_move

    old_pos_dict = johann_emission._forward({'energy': energy})
    rowland_circle.R = new_R

    if energy is None:
        energy = johann_emission.energy.position
    new_pos_dict = johann_emission._forward({'energy': energy})
    for motor in motors_to_move:
        motor_obj = getattr(johann_emission, motor)
        # print(motor, new_pos_dict[motor], f'delta={new_pos_dict[motor] - old_pos_dict[motor]}')
        # motor_obj.move(new_pos_dict[motor])
        yield from bps.mv(motor_obj, new_pos_dict[motor])

_alignment_strategy_to_plan_dict = {'emission': {'fly': 'epics_fly_scan_johann_emission_alignment_plan_bundle'},
                                    'elastic': {'fly': 'fly_scan_johann_elastic_alignment_plan_bundle'},
                                    'herfd': {'fly': 'fly_scan_johann_herfd_alignment_plan_bundle'}}

def johann_tweak_crystal_and_scan_plan_bundle(crystal=None, scan_range_alignment_multiplier=None,
                                              alignment_data=None,
                                              motor_info=None,
                                              mono_energy=None,
                                              tweak_motor_axis=None, tweak_motor_range=None, tweak_motor_num_steps=None,
                                              alignment_strategy=None, scan_kind=None,
                                              pil100k_roi_num=None,
                                              yaw_tune=True, yaw_tune_range=800, yaw_tune_duration=10, yaw_tune_step=10,
                                              yaw_tune_exposure=0.25,
                                              roll_tune=False, roll_tune_range=800, roll_tune_duration=10,
                                              roll_tune_step=10,
                                              roll_tune_exposure=0.25,
                                              scan_range=800, scan_duration=10, scan_step=10, scan_exposure=0.25,
                                              herfd_scan_element='', herfd_scan_edge='', md=None,
                                              plot_func=None, liveplot_kwargs=None):
    plans = []

    plans.append({'plan_name': 'johann_focus_on_one_crystal_plan', 'plan_kwargs': {'crystal': crystal}})

    if alignment_data is None:
        alignment_data = []

    if md is None:
        md = {}

    if scan_range_alignment_multiplier is None:
        _tweak_motor_range = tweak_motor_range
    else:
        _tweak_motor_range = tweak_motor_range * scan_range_alignment_multiplier
    tweak_motor_init_pos, tweak_motor_pos, tweak_motor_description = get_tweak_motor_positions_for_crystal(crystal,
                                                                                                           tweak_motor_axis,
                                                                                                           _tweak_motor_range,
                                                                                                           tweak_motor_num_steps)

    if mono_energy is None: mono_energy = hhm.energy.position
    yaw_init_position = get_johann_crystal_axis_motor_pos(crystal, 'yaw')

    for i, _pos in enumerate(tweak_motor_pos):
        plans.append({'plan_name': 'print_message_plan',
                      'plan_kwargs': {
                          'msg': f'Motor {tweak_motor_description} in position={_pos}) (step {i + 1}/{len(tweak_motor_pos)}',
                          'add_timestamp': True,
                          'tag': 'Spectrometer'}})
        plans.append({'plan_name': 'move_motor_plan',
                      'plan_kwargs': {'motor_attr': tweak_motor_description,
                                      'based_on': 'description',
                                      'position': _pos}})

        plans.append({'plan_name': 'move_motor_plan',
                      'plan_kwargs': {'motor_attr': 'A Monochromator Energy',
                                      'based_on': 'description',
                                      'position': mono_energy}})

        # pretune yaw
        if (crystal != 'main') and yaw_tune:
            yaw_tune_params = {'scan_range': yaw_tune_range}
            if scan_kind == 'fly':
                yaw_tune_params['duration'] = yaw_tune_duration
            elif scan_kind == 'step':
                yaw_tune_params['step_size'] = yaw_tune_step
                yaw_tune_params['exposure_time'] = yaw_tune_exposure

            plans.append({'plan_name': 'tune_johann_piezo_plan',
                          'plan_kwargs': {'property': 'com',
                                          'pil100k_roi_num': pil100k_roi_num,
                                          'scan_kind': scan_kind,
                                          'crystal': crystal,
                                          'axis': 'yaw',
                                          **yaw_tune_params,
                                          'plot_func': plot_func,
                                          'liveplot_kwargs': liveplot_kwargs}})

        # pretune roll
        if roll_tune:
            roll_tune_params = {'scan_range': roll_tune_range}
            if scan_kind == 'fly':
                roll_tune_params['duration'] = roll_tune_duration
            elif scan_kind == 'step':
                roll_tune_params['step_size'] = roll_tune_step
                roll_tune_params['exposure_time'] = roll_tune_exposure
            plans.append({'plan_name': 'tune_johann_piezo_plan',
                          'plan_kwargs': {'property': 'com',
                                          'pil100k_roi_num': pil100k_roi_num,
                                          'scan_kind': scan_kind,
                                          'crystal': crystal,
                                          'axis': 'roll',
                                          **roll_tune_params,
                                          'plot_func': plot_func,
                                          'liveplot_kwargs': liveplot_kwargs}})

        _md = {**md}
        if ('tweak_motor_description' not in _md.keys()) and ('tweak_motor_position' not in _md.keys()):
            _md = {'tweak_motor_description': tweak_motor_description,
                   'tweak_motor_position': _pos,
                   **_md}
        if ('alignment_crystal' not in _md.keys()):
            _md = {'alignment_crystal': crystal,
                   **_md}

        alignment_plan_kwargs = {'scan_range': scan_range}
        if scan_kind == 'fly':
            alignment_plan_kwargs['duration'] = scan_duration
        elif scan_kind == 'step':
            alignment_plan_kwargs['step_size'] = scan_step
            alignment_plan_kwargs['exposure_time'] = scan_exposure

        if alignment_strategy == 'emission':
            alignment_plan_kwargs['mono_energy'] = mono_energy

        elif alignment_strategy == 'elastic':
            alignment_plan_kwargs['e_cen'] = mono_energy

        elif alignment_strategy == 'herfd':
            alignment_plan_kwargs = {'element': herfd_scan_element,
                                     'edge': herfd_scan_edge}
        if motor_info is None:
            motor_info = f'{tweak_motor_description}={_pos: 0.2f}'
        plans.append({'plan_name': 'johann_alignment_scan_plan_bundle',
                      'plan_kwargs': {'rois': [pil100k_roi_num],
                                      'liveplot_kwargs': liveplot_kwargs,
                                      'alignment_data': alignment_data,
                                      'md': _md,
                                      'motor_info': motor_info,
                                      'alignment_plan': _alignment_strategy_to_plan_dict[alignment_strategy][scan_kind],
                                      'crystal': crystal,
                                      **alignment_plan_kwargs}})

    plans.append({'plan_name': 'undo_johann_focus_on_one_crystal_plan', 'plan_kwargs': {'crystal': crystal}})

    plans.append({'plan_name': 'print_message_plan',
                  'plan_kwargs': {
                      'msg': f'Returning motor {tweak_motor_description} to initial position={tweak_motor_init_pos})',
                      'add_timestamp': True,
                      'tag': 'Spectrometer'}})
    plans.append({'plan_name': 'move_motor_plan',
                  'plan_kwargs': {'motor_attr': tweak_motor_description,
                                  'based_on': 'description',
                                  'position': tweak_motor_init_pos}})
    plans.append({'plan_name': 'move_motor_plan',
                  'plan_kwargs': {'motor_attr': 'A Monochromator Energy',
                                  'based_on': 'description',
                                  'position': mono_energy}})
    if crystal != 'main':
        plans.append({'plan_name': 'move_motor_plan',
                      'plan_kwargs': {'motor_attr': _crystal_alignment_dict[crystal]['yaw'],
                                      'based_on': 'description',
                                      'position': yaw_init_position}})

    return plans


def johann_spectrometer_run_alignment_scans_vs_R_plans(
        crystals: list,
        alignment_data: list,
        R_range: float, R_num_steps: int, spectrometer_nominal_energy: float,
        mono_energy: float,
        automatic_mode: bool,
        automatic_fom: str,
        **kwargs):
    plans = []

    R_init = rowland_circle.R
    Rs = np.linspace(R_init - R_range / 2, R_init + R_range / 2, R_num_steps)

    for j, _R in enumerate(Rs):
        plans.append({'plan_name': 'print_message_plan',
                      'plan_kwargs': {'msg': f'Aligning for R={_R} (step {j + 1}/{R_num_steps})',
                                      'add_timestamp': True,
                                      'tag': 'Spectrometer'}})

        plans.append({'plan_name': 'move_rowland_circle_R_plan',
                      'plan_kwargs': {'new_R': _R,
                                      'energy': spectrometer_nominal_energy}})


        for i, crystal in enumerate(crystals):

            plans.append({'plan_name': 'print_message_plan',
                          'plan_kwargs': {'msg': f'Aligning {crystal} crystal (step {i + 1}/{len(crystals)}).',
                                          'add_timestamp': True,
                                          'tag': 'Spectrometer'}})

            plans.append({'plan_name': 'johann_tweak_crystal_and_scan_plan_bundle',
                          'plan_kwargs': {'crystal': crystal,
                                          'scan_range_alignment_multiplier': None,
                                          'alignment_data': alignment_data,
                                          'motor_info': f'R={_R: 0.2f}',
                                          'mono_energy': mono_energy,
                                          'tweak_motor_axis': 'x',
                                          'tweak_motor_range': 0,
                                          'tweak_motor_num_steps': 1,
                                          'md': {'tweak_motor_description': 'Rowland Circle Radius',
                                                 'tweak_motor_position': _R,
                                                 'scan_scope': 'alignment'},
                                          **kwargs}})

    if automatic_mode:
        pass
    else:
        plans.append({'plan_name': 'print_message_plan',
                      'plan_kwargs': {'msg': f'Returning R to initial position={R_init})',
                                      'add_timestamp': True,
                                      'tag': 'Spectrometer'}})
        plans.append({'plan_name': 'move_rowland_circle_R_plan',
                      'plan_kwargs': {'new_R': R_init,
                                      'energy': spectrometer_nominal_energy}})

    return plans


# ALIGNMENT_DATA = {}
# plans = johann_spectrometer_run_alignment_scans_vs_R_plans(
#                                               alignment_data=ALIGNMENT_DATA,
#                                               spectrometer_energy=9989, R_range=0, R_num_steps=1,
#                                               alignment_by='elastic', scan_kind='fly',
#                                               pil100k_roi_num=1,
#                                               exposure_time=0.5,
#                                               scan_range_yaw=1000, scan_step_yaw=10, scan_duration_yaw=10,
#                                               scan_range_roll=1000, scan_step_roll=None, scan_duration_roll=10,
#                                               scan_range_mono=12, scan_step_mono=None, scan_duration_mono=10,
#                                               herfd_element=None, herfd_edge=None, scan_duration_herfd=None,
#                                               plot_func=None, liveplot_kwargs=None)
# plan_processor.add_plans(plans)

def johann_spectrometer_run_alignment_scans_vs_x_plans(
        crystals: list,
        alignment_data: list,
        x_range: float, x_num_steps: int,
        mono_energy: float,
        automatic_mode: bool,
        automatic_fom: str,
        **kwargs):

    plans = []
    for crystal in crystals:
        multiplier = 1 if crystal == 'main' else 1000
        plans.append({'plan_name': 'johann_tweak_crystal_and_scan_plan_bundle',
                      'plan_kwargs': {'crystal': crystal,
                                      'scan_range_alignment_multiplier': multiplier,
                                      'alignment_data': alignment_data[crystal],
                                      'mono_energy': mono_energy,
                                      'tweak_motor_axis': 'x',
                                      'tweak_motor_range': x_range,
                                      'tweak_motor_num_steps': x_num_steps,
                                      'md': {'scan_scope': 'alignment'},
                                      **kwargs}})

        # in automatic mode it is important that if main crystal is enabled, it should be optimized first
        # that is currently enforced in the parent plans calling this one
        if automatic_mode:
            _alignment_plan = _alignment_strategy_to_plan_dict[kwargs['alignment_strategy']][kwargs['scan_kind']]
            analysis_kwargs = {'alignment_data': alignment_data,
                               'scan_scope': 'alignment',
                               'alignment_plan': _alignment_plan,
                               'crystal': crystal}
            plans.append({'plan_name': 'johann_analyze_alignment_data_plan',
                          'plan_kwargs': analysis_kwargs})
            plans.append({'plan_name': 'move_to_optimal_crystal_alignment_position_plan',
                          'plan_kwargs': {**analysis_kwargs,
                                          'fom': automatic_fom}})


    return plans


# ALIGNMENT_DATA = {}
# plans = johann_crystal_alignment_plan_bundle(crystal='aux3', scan_range_alignment_multiplier=1000,
#                                          alignment_data=ALIGNMENT_DATA,
#                                          tweak_motor_axis='x', tweak_motor_range=10, tweak_motor_num_steps=5,
#                                          alignment_by='elastic', scan_kind='fly',
#                                          pil100k_roi_num=1,
#                                          exposure_time=0.25,
#                                          scan_range_yaw=1000, scan_step_yaw=10, scan_duration_yaw=10,
#                                          scan_range_roll=1000, scan_step_roll=None, scan_duration_roll=10,
#                                          scan_range_mono=25, scan_step_mono=None, scan_duration_mono=60,
#                                          herfd_element='U', herfd_edge='L3', scan_duration_herfd=45,
#                                          plot_func=None, liveplot_kwargs=None)
# plan_processor.add_plans(plans)

def johann_spectrometer_alignment_plan_bundle(
        crystals=None,
        alignment_data=None,
        alignment_motor=None,
        motor_range=None, motor_num_steps=None,
        spectrometer_nominal_energy=None,
        automatic_mode=False,
        automatic_fom='max',
        post_tuning=True,
        **kwargs):

    plans = []

    if alignment_data is None:
        alignment_data = johann_emission.alignment_data

    if crystals is None:
        crystals = johann_emission.enabled_crystals_list

    mono_energy = hhm.energy.position

    plans.append({'plan_name': 'print_message_plan',
                  'plan_kwargs': {
                      'msg': f'Starting the spectrometer alignment.',
                      'add_timestamp': True,
                      'tag': 'Spectrometer'}})

    if alignment_motor == 'R':
        _plans = johann_spectrometer_run_alignment_scans_vs_R_plans(
            crystals=crystals,
            alignment_data=alignment_data,
            R_range=motor_range, R_num_steps=motor_num_steps, spectrometer_nominal_energy=spectrometer_nominal_energy,
            mono_energy=mono_energy,
            automatic_mode=automatic_mode,
            automatic_fom=automatic_fom,
            **kwargs)

    elif alignment_motor == 'X':
        _plans = johann_spectrometer_run_alignment_scans_vs_x_plans(
            crystals=crystals,
            alignment_data=alignment_data,
            x_range=motor_range, x_num_steps=motor_num_steps,
            mono_energy=mono_energy,
            automatic_mode=automatic_mode,
            automatic_fom=automatic_fom,
            **kwargs)
    else:
        raise NotImplementedError('Alignment can be performed only by X and R!')

    plans.extend(_plans)

    if post_tuning:
        plans.append({'plan_name': 'print_message_plan',
                      'plan_kwargs': {
                          'msg': f'Performing post-alignment yaw motor tuning)',
                          'add_timestamp': True,
                          'tag': 'Spectrometer'}})

        for crystal in crystals:
            if (crystal != 'main') and kwargs['yaw_tune']:
                yaw_tune_params = {'scan_range': kwargs['yaw_tune_range']}
                if kwargs['scan_kind'] == 'fly':
                    yaw_tune_params['duration'] = kwargs['yaw_tune_duration']
                elif kwargs['scan_kind'] == 'step':
                    yaw_tune_params['step_size'] = kwargs['yaw_tune_step']
                    yaw_tune_params['exposure_time'] = kwargs['yaw_tune_exposure']

                plans.append({'plan_name': 'tune_johann_piezo_plan',
                              'plan_kwargs': {'property': 'com',
                                              'pil100k_roi_num': kwargs['pil100k_roi_num'],
                                              'scan_kind': kwargs['scan_kind'],
                                              'crystal': crystal,
                                              'axis': 'yaw',
                                              **yaw_tune_params,
                                              'plot_func': kwargs['plot_func'],
                                              'liveplot_kwargs': kwargs['liveplot_kwargs']}})

    plans.append({'plan_name': 'print_message_plan',
                  'plan_kwargs': {
                      'msg': f'Spectrometer alignment is complete.',
                      'add_timestamp': True,
                      'tag': 'Spectrometer'}})

    return plans
#
'''
ALIGNMENT_DATA = []
plans = johann_spectrometer_alignment_plan_bundle(
        alignment_data=ALIGNMENT_DATA,
        alignment_motor='R',
        motor_range=12, motor_num_steps=4,
        spectrometer_nominal_energy=9989,
        post_tuning=False,
        alignment_strategy='elastic', scan_kind='fly',
        pil100k_roi_num=1,
        yaw_tune=True, yaw_tune_range=800, yaw_tune_duration=5,
        roll_tune=False, roll_tune_range=800, roll_tune_duration=10,
        scan_range=15, scan_duration=10,
        herfd_scan_element='', herfd_scan_edge='')
plan_processor.add_plans(plans)
'''

    #     # plans.append({'plan_name': 'move_to_optimal_crystal_alignment_position_plan',
    #     #               'plan_kwargs': {'alignment_data': alignment_data[crystal],
    #     #                               'fom': _scan_fom_dict[kwargs['alignment_by']]['alignment']['fom'],
    #     #                               'polarity': _scan_fom_dict[kwargs['alignment_by']]['alignment']['polarity']}})
    #

    #
    # scan_range_yaw = kwargs['scan_range_yaw']
    # scan_duration_yaw = kwargs['scan_duration_yaw']
    # scan_step_yaw = kwargs['scan_step_yaw']
    # exposure_time = kwargs['exposure_time']
    # pil100k_roi_num = kwargs['pil100k_roi_num']
    # scan_kind = kwargs['scan_kind']
    # plot_func = kwargs['plot_func']
    # liveplot_kwargs = kwargs['liveplot_kwargs']
    #
    # for crystal in enabled_crystals:
    #     if crystal != 'main':
    #         # pretune yaw
    #         plans.append({'plan_name': 'move_motor_plan',
    #                       'plan_kwargs': {'motor_attr': 'A Monochromator Energy',
    #                                       'based_on': 'description',
    #                                       'position': mono_energy}})
    #         yaw_scan_params = {'scan_range': scan_range_yaw}
    #         if scan_kind == 'fly':
    #             yaw_scan_params['duration'] = scan_duration_yaw
    #         elif scan_kind == 'step':
    #             yaw_scan_params['step_size'] = scan_step_yaw
    #             yaw_scan_params['exposure_time'] = exposure_time
    #
    #         plans.append({'plan_name': 'tune_johann_piezo_plan',
    #                       'plan_kwargs': {'property': 'com',
    #                                       'pil100k_roi_num': pil100k_roi_num,
    #                                       'scan_kind': scan_kind,
    #                                       'crystal': crystal,
    #                                       'axis': 'yaw',
    #                                       'scan_range': scan_range_yaw,
    #                                       **yaw_scan_params,
    #                                       'plot_func': plot_func,
    #                                       'liveplot_kwargs': liveplot_kwargs}})
    #
    # plans.append({'plan_name': 'print_message_plan',
    #               'plan_kwargs': {
    #                   'msg': f'Spectrometer alignment is complete.',
    #                   'add_timestamp': True,
    #                   'tag': 'Spectrometer'}})




# ALIGNMENT_DATA = []
#
# plans = []
# plans.append({'plan_name': 'johann_crystal_alignment_plan_bundle',
#               'plan_kwargs': {'crystal': 'aux5', 'scan_range_alignment_multiplier': 1000,
#                               'alignment_data': ALIGNMENT_DATA,
#                               'tweak_motor_axis': 'x', 'tweak_motor_range': 30, 'tweak_motor_num_steps': 11,
#                               'alignment_by': 'emission', 'scan_kind': 'fly',
#                               'pil100k_roi_num': 1,
#                               'exposure_time': None,
#                               'scan_range_yaw': 1000, 'scan_step_yaw': 20, 'scan_duration_yaw': 10,
#                               'scan_range_roll': 1000, 'scan_step_roll': None, 'scan_duration_roll': 10,
#                               'scan_range_mono': 15, 'scan_step_mono': 0.1, 'scan_duration_mono': 10,
#                               'herfd_element': 'Cu', 'herfd_edge': 'K', 'scan_duration_herfd': 10,
#                               'plot_func': None, 'liveplot_kwargs': None}})
# ALIGNMENT_DATA = {}
#
# plans = []
# for crystal in ['aux3', 'aux4', 'aux5']:
#     ALIGNMENT_DATA[crystal] = []
#     plans.append({'plan_name': 'johann_crystal_alignment_plan_bundle',
#                   'plan_kwargs': {'crystal': crystal, 'scan_range_alignment_multiplier': 1000,
#                                                  'alignment_data': ALIGNMENT_DATA[crystal],
#                                                  'tweak_motor_axis': 'x', 'tweak_motor_range': 30, 'tweak_motor_num_steps': 15,
#                                                  'alignment_by': 'emission', 'scan_kind': 'fly',
#                                                  'pil100k_roi_num': 1,
#                                                  'exposure_time': None,
#                                                  'scan_range_yaw': 500, 'scan_step_yaw': 20, 'scan_duration_yaw': 10,
#                                                  'scan_range_roll': 1000, 'scan_step_roll': None, 'scan_duration_roll': 10,
#                                                  'scan_range_mono': 15, 'scan_step_mono': 0.1, 'scan_duration_mono': 10,
#                                                  'herfd_element': 'Cu', 'herfd_edge': 'K', 'scan_duration_herfd': 10,
#                                                  'plot_func': None, 'liveplot_kwargs': None}})
# plan_processor.add_plans(plans)

# ALIGNMENT_DATA = []
# plans = []
#
# plans.append({'plan_name': 'move_sample_stage_plan', # Cu foil
#    'plan_kwargs': {'sample_coordinates': {'x': 23.309,
#      'y': -45.664,
#      'z': 7.0,
#      'th': 80.364}},
#    'plan_description': 'move_sample_stage_plan'})
#
# for alignment_by in ['emission', 'herfd']:
#
#     plans.append({'plan_name': 'move_motor_plan',
#                   'plan_kwargs': {'motor_attr': 'A Monochromator Energy',
#                                   'based_on': 'description',
#                                   'position': 9000}})
#     plans.append({'plan_name': 'johann_crystal_alignment_plan_bundle',
#                   'plan_kwargs': {'crystal': 'main', 'scan_range_alignment_multiplier': 1,
#                                                  'alignment_data': ALIGNMENT_DATA,
#                                                  'tweak_motor_axis': 'x', 'tweak_motor_range': 25, 'tweak_motor_num_steps': 25,
#                                                  'alignment_by': alignment_by, 'scan_kind': 'fly',
#                                                  'pil100k_roi_num': 1,
#                                                  'exposure_time': None,
#                                                  'scan_range_yaw': 1000, 'scan_step_yaw': 20, 'scan_duration_yaw': 10,
#                                                  'scan_range_roll': 1000, 'scan_step_roll': None, 'scan_duration_roll': 10,
#                                                  'scan_range_mono': 15, 'scan_step_mono': 0.1, 'scan_duration_mono': 10,
#                                                  'herfd_element': 'Cu', 'herfd_edge': 'K', 'scan_duration_herfd': 10,
#                                                  'plot_func': None, 'liveplot_kwargs': None}})
#
#
#     for i in range(2, 6):
#         plans.append({'plan_name': 'johann_crystal_alignment_plan_bundle',
#                       'plan_kwargs': {'crystal': f'aux{i}', 'scan_range_alignment_multiplier': 1000,
#                                       'alignment_data': ALIGNMENT_DATA,
#                                       'tweak_motor_axis': 'x', 'tweak_motor_range': 30, 'tweak_motor_num_steps': 30,
#                                       'alignment_by': alignment_by, 'scan_kind': 'fly',
#                                       'pil100k_roi_num': 1,
#                                       'exposure_time': None,
#                                       'scan_range_yaw': 1000, 'scan_step_yaw': 20, 'scan_duration_yaw': 10,
#                                       'scan_range_roll': 1000, 'scan_step_roll': None, 'scan_duration_roll': 10,
#                                       'scan_range_mono': 15, 'scan_step_mono': 0.1, 'scan_duration_mono': 10,
#                                       'herfd_element': 'Cu', 'herfd_edge': 'K', 'scan_duration_herfd': 10,
#                                       'plot_func': None, 'liveplot_kwargs': None}})
#
#
# plans.append({'plan_name': 'move_motor_plan',
#                       'plan_kwargs': {'motor_attr': 'A Monochromator Energy',
#                                       'based_on': 'description',
#                                       'position': 8046}})
#
#
# sample_move_plans = \
# [{'plan_name': 'move_sample_stage_plan', # Cu foil
#    'plan_kwargs': {'sample_coordinates': {'x': 23.309,
#      'y': -45.664,
#      'z': 7.0,
#      'th': 80.364}},
#    'plan_description': 'move_sample_stage_plan'},
#
#  {'plan_name': 'move_sample_stage_plan', # w foil
#    'plan_kwargs': {'sample_coordinates': {'x': 28.316,
#      'y': -71.268,
#      'z': 7.0,
#      'th': 80.364}},
#    'plan_description': 'move_sample_stage_plan'},
#
#  {'plan_name': 'move_sample_stage_plan', # water
#    'plan_kwargs': {'sample_coordinates': {'x': -21.519,
#      'y': -63.759,
#      'z': 6.38,
#      'th': 80.364}},
#    'plan_description': 'move_sample_stage_plan'},
#
#  {'plan_name': 'move_sample_stage_plan', # zeolite
#    'plan_kwargs': {'sample_coordinates': {'x': -26.11,
#      'y': -63.759,
#      'z': 7.31,
#      'th': 80.364}},
#    'plan_description': 'move_sample_stage_plan'},
#
#  {'plan_name': 'move_sample_stage_plan', # plastic
#    'plan_kwargs': {'sample_coordinates': {'x': -14.021,
#      'y': -63.976,
#      'z': 6.38,
#      'th': 80.364}},
#    'plan_description': 'move_sample_stage_plan'},
#  ]
#
# for sample_move_plan in sample_move_plans:
#     plans.append(sample_move_plan)
#
#     plans.append({'plan_name': 'johann_crystal_alignment_plan_bundle',
#                   'plan_kwargs': {'crystal': 'main', 'scan_range_alignment_multiplier': 1,
#                                   'alignment_data': ALIGNMENT_DATA,
#                                   'tweak_motor_axis': 'x', 'tweak_motor_range': 25, 'tweak_motor_num_steps': 25,
#                                   'alignment_by': 'elastic', 'scan_kind': 'fly',
#                                   'pil100k_roi_num': 1,
#                                   'exposure_time': None,
#                                   'scan_range_yaw': 1000, 'scan_step_yaw': 20, 'scan_duration_yaw': 10,
#                                   'scan_range_roll': 1000, 'scan_step_roll': None, 'scan_duration_roll': 10,
#                                   'scan_range_mono': 15, 'scan_step_mono': 0.1, 'scan_duration_mono': 10,
#                                   'herfd_element': 'Cu', 'herfd_edge': 'K', 'scan_duration_herfd': 10,
#                                   'plot_func': None, 'liveplot_kwargs': None}})
#
#     for i in range(2, 6):
#         plans.append({'plan_name': 'johann_crystal_alignment_plan_bundle',
#                       'plan_kwargs': {'crystal': f'aux{i}', 'scan_range_alignment_multiplier': 1000,
#                                       'alignment_data': ALIGNMENT_DATA,
#                                       'tweak_motor_axis': 'x', 'tweak_motor_range': 30, 'tweak_motor_num_steps': 30,
#                                       'alignment_by': 'elastic', 'scan_kind': 'fly',
#                                       'pil100k_roi_num': 1,
#                                       'exposure_time': None,
#                                       'scan_range_yaw': 1000, 'scan_step_yaw': 20, 'scan_duration_yaw': 10,
#                                       'scan_range_roll': 1000, 'scan_step_roll': None, 'scan_duration_roll': 10,
#                                       'scan_range_mono': 15, 'scan_step_mono': 0.1, 'scan_duration_mono': 10,
#                                       'herfd_element': 'Cu', 'herfd_edge': 'K', 'scan_duration_herfd': 10,
#                                       'plot_func': None, 'liveplot_kwargs': None}})
#
#
#
# plan_processor.add_plans(plans)

# ALIGNMENT_DATA = []
# plans = run_alignment_scans_for_crystal_bundle(crystal='main', alignment_by='elastic', pil100k_roi_num=1,
#                                            alignment_data=ALIGNMENT_DATA,
#                                            scan_range_roll=12, scan_range_yaw=400, step_size=10,
#                                            exposure_time = 0.5,
#                                            tweak_motor_range=20, tweak_motor_num_steps=9,
#                                            plot_func=None, liveplot_kwargs=None)

# plans = run_alignment_scans_for_crystal_bundle(crystal='aux2', alignment_by='elastic', pil100k_roi_num=1,
#                                            alignment_data=ALIGNMENT_DATA,
#                                            scan_range_roll=12, scan_range_yaw=600, step_size=20,
#                                            exposure_time = 0.3,
#                                            tweak_motor_range=24000, tweak_motor_num_steps=11,
#                                            plot_func=None, liveplot_kwargs=None)

# plans = run_alignment_scans_for_crystal_bundle(crystal='main', alignment_by='emission', pil100k_roi_num=1,
#                                                alignment_data=ALIGNMENT_DATA,
#                                                scan_range_roll=800, scan_range_yaw=400, step_size=10,
#                                                exposure_time = 0.3,
#                                                tweak_motor_range=15, tweak_motor_num_steps=7,
#                                                plot_func=None, liveplot_kwargs=None)

# plans = run_alignment_scans_for_crystal_bundle(crystal='aux5', alignment_by='emission', pil100k_roi_num=1,
#                                            alignment_data=ALIGNMENT_DATA,
#                                            scan_range_roll=800, scan_range_yaw=600, step_size=10,
#                                            exposure_time = 0.3,
#                                            tweak_motor_range=10000, tweak_motor_num_steps=5,
#                                            plot_func=None, liveplot_kwargs=None)


#
# def johann_spectrometer_alignment_plan_bundle(**kwargs):
#     plans = []
#
#     alignment_data = johann_emission.alignment_data
#     enabled_crystals = johann_emission.enabled_crystals_list
#
#     mono_energy = hhm.energy.position
#
#     plans.append({'plan_name': 'print_message_plan',
#                   'plan_kwargs': {
#                       'msg': f'Starting the spectrometer alignment.',
#                       'add_timestamp': True,
#                       'tag': 'Spectrometer'}})
#
#     for crystal in enabled_crystals:
#         if crystal not in alignment_data.keys():
#             alignment_data[crystal] = []
#
#         plans.append({'plan_name': 'print_message_plan',
#                       'plan_kwargs': {'msg': f'Aligning {crystal} crystal.',
#                                       'add_timestamp': True,
#                                       'tag': 'Spectrometer'}})
#
#         multiplier = 1 if crystal == 'main' else 1000
#         plans.append({'plan_name': 'johann_crystal_alignment_plan_bundle',
#                       'plan_kwargs': {'crystal': crystal,
#                                       'scan_range_alignment_multiplier': multiplier,
#                                       'alignment_data': alignment_data[crystal],
#                                       'tweak_motor_axis': 'x',
#                                       **kwargs}})
#         plans.append({'plan_name': 'move_to_optimal_crystal_alignment_position_plan',
#                       'plan_kwargs': {'alignment_data': alignment_data[crystal],
#                                       'fom': _scan_fom_dict[kwargs['alignment_by']]['alignment']['fom'],
#                                       'polarity': _scan_fom_dict[kwargs['alignment_by']]['alignment']['polarity']}})
#
#     plans.append({'plan_name': 'print_message_plan',
#                   'plan_kwargs': {
#                       'msg': f'Performing post-alignment yaw motor tuning)',
#                       'add_timestamp': True,
#                       'tag': 'Spectrometer'}})
#
#     scan_range_yaw = kwargs['scan_range_yaw']
#     scan_duration_yaw = kwargs['scan_duration_yaw']
#     scan_step_yaw = kwargs['scan_step_yaw']
#     exposure_time = kwargs['exposure_time']
#     pil100k_roi_num = kwargs['pil100k_roi_num']
#     scan_kind = kwargs['scan_kind']
#     plot_func = kwargs['plot_func']
#     liveplot_kwargs = kwargs['liveplot_kwargs']
#
#     for crystal in enabled_crystals:
#         if crystal != 'main':
#             # pretune yaw
#             plans.append({'plan_name': 'move_motor_plan',
#                           'plan_kwargs': {'motor_attr': 'A Monochromator Energy',
#                                           'based_on': 'description',
#                                           'position': mono_energy}})
#             yaw_scan_params = {'scan_range': scan_range_yaw}
#             if scan_kind == 'fly':
#                 yaw_scan_params['duration'] = scan_duration_yaw
#             elif scan_kind == 'step':
#                 yaw_scan_params['step_size'] = scan_step_yaw
#                 yaw_scan_params['exposure_time'] = exposure_time
#
#             plans.append({'plan_name': 'tune_johann_piezo_plan',
#                           'plan_kwargs': {'property': 'com',
#                                           'pil100k_roi_num': pil100k_roi_num,
#                                           'scan_kind': scan_kind,
#                                           'crystal': crystal,
#                                           'axis': 'yaw',
#                                           'scan_range': scan_range_yaw,
#                                           **yaw_scan_params,
#                                           'plot_func': plot_func,
#                                           'liveplot_kwargs': liveplot_kwargs}})
#
#     plans.append({'plan_name': 'print_message_plan',
#                   'plan_kwargs': {
#                       'msg': f'Spectrometer alignment is complete.',
#                       'add_timestamp': True,
#                       'tag': 'Spectrometer'}})
#
#     return plans
#
# #consider having short
# def johann_spectrometer_calibration_plan_bundle(calibrate_by=None, scan_kind=None,
#                                                 pil100k_roi_num=None,
#                                                 calibration_data=None,
#                                                 exposure_time=None,
#                                                 scan_range_roll=None, scan_step_roll=None, scan_duration_roll=None, # scan range roll better be small for this
#                                                 herfd_element=None, herfd_edge=None, scan_duration_herfd=None,
#                                                 liveplot_kwargs=None):
#
#     enabled_crystals = johann_emission.enabled_crystals_list
#
#     if calibration_data is None:
#         calibration_data = {}
#
#     plans = []
#
#     plans.append({'plan_name': 'print_message_plan',
#                   'plan_kwargs': {
#                       'msg': f'Starting the spectrometer calibration.',
#                       'add_timestamp': True,
#                       'tag': 'Spectrometer'}})
#
#     if calibrate_by == 'roll':
#         for crystal in enabled_crystals:
#             scan_params = {'scan_range': scan_range_roll}
#             if scan_kind == 'fly':
#                 scan_params['duration'] = scan_duration_roll
#             elif scan_kind == 'step':
#                 scan_params['step_size'] = scan_step_roll
#                 scan_params['exposure_time'] = exposure_time
#
#             plans.append({'plan_name': 'tune_johann_piezo_plan',
#                           'plan_kwargs': {'scan_kind': scan_kind,
#                                           'crystal': crystal,
#                                           'axis': 'roll',
#                                           'liveplot_kwargs': liveplot_kwargs,
#                                           'pil100k_roi_num': pil100k_roi_num,
#                                           **scan_params}})
#
#     elif calibrate_by == 'herfd':
#         scan_kwargs = {'scan_range_alignment_multiplier': 1,
#                        'tweak_motor_axis': 'roll',
#                        'alignment_by': 'herfd',
#                        'scan_kind': scan_kind,
#                        'pil100k_roi_num': pil100k_roi_num,
#                        'exposure_time': exposure_time,
#                        'herfd_element': herfd_element,
#                        'herfd_edge': herfd_edge,
#                        'scan_duration_herfd': scan_duration_herfd,
#                        'liveplot_kwargs': liveplot_kwargs}
#
#         calibration_data[enabled_crystals[0]] = []
#         plans.append({'plan_name': 'johann_crystal_alignment_plan_bundle',
#                       'plan_kwargs': {'crystal': enabled_crystals[0],
#                                       'tweak_motor_range': 0,
#                                       'tweak_motor_num_steps': 1,
#                                       'alignment_data': calibration_data[enabled_crystals[0]],
#                                       **scan_kwargs}})
#
#         for crystal in enabled_crystals[1:]:
#             plans.append({'plan_name': 'johann_crystal_alignment_plan_bundle',
#                           'plan_kwargs': {'crystal': crystal,
#                                           'tweak_motor_range': scan_range_roll,
#                                           'tweak_motor_num_steps': int(scan_range_roll / scan_step_roll) + 1,
#                                           **scan_kwargs}})
#
#             # perform analysis on the calibration data
#             plans.append({'plan_name': 'johann_analyze_herfd_calibration_data_plan',
#                           'plan_kwargs': {'calibration_data': calibration_data, 'liveplot_kwargs': liveplot_kwargs}})
#
#             plans.append({'plan_name': 'move_to_optimal_crystal_alignment_position_plan',
#                           'plan_kwargs': {'alignment_data': calibration_data[crystal],
#                                           'fom': _scan_fom_dict['herfd']['calibration']['fom'],
#                                           'polarity': _scan_fom_dict['herfd']['calibration']['polarity']}})
#
#     plans.append({'plan_name': 'print_message_plan',
#                   'plan_kwargs': {
#                       'msg': f'Spectrometer calibration is complete.',
#                       'add_timestamp': True,
#                       'tag': 'Spectrometer'}})
#
#     return plans
#
#
# def johann_analyze_spectrometer_resolution_plan(resolution_data=None, fom=None):
#     fwhms = []
#     print_to_gui('')
#     for crystal, scan_result in resolution_data.items():
#         print_to_gui(f'Resolution for {crystal} crystal is {scan_result[fom]}')
#         fwhms.append(scan_result[fom])
#     print_to_gui('')
#     print_to_gui(f'The average spectrometer resolution is {np.mean(fwhms): 0.2f} eV.')
#     print_to_gui('')
#     yield from bps.null()
#
# def johann_measure_spectrometer_resolution_plan_bundle(**kwargs):
#     plans = []
#     resolution_data = {}
#     fom = _scan_fom_dict['elastic']['alignment']
#
#     enabled_crystals = johann_emission.enabled_crystals_list
#     for crystal in enabled_crystals:
#         plans.append({'plan_name': 'johann_focus_on_one_crystal_plan', 'plan_kwargs': {'crystal': crystal}})
#         plans.append({'plan_name': 'johann_alignment_scan_plan_bundle',
#                       'plan_kwargs': {'crystal': crystal,
#                                       'alignment_plan': 'fly_scan_johann_elastic_alignment_plan_bundle',
#                                       'fom': fom,
#                                       'alignment_data': resolution_data,
#                                       **kwargs}})
#
#         plans.append({'plan_name': 'undo_johann_focus_on_one_crystal_plan', 'plan_kwargs': {'crystal': crystal}})
#
#     plans.append({'plan_name': 'estimate_spectrometer_resolution_plan',
#                   'plan_kwargs': {'resolution_data': resolution_data,
#                                   'fom': fom}})
#
#     return plans


# plans = []
# plans.extend(johann_measure_spectrometer_resolution_plan_bundle(e_cen=8340, scan_range=12, duration=20, motor_info='resolution', md={}))
# plan_processor.add_plans(plans)
#
# bla=[]
# plans = []
# # plans.append({'plan_name': 'johann_focus_on_one_crystal_plan', 'plan_kwargs': {'crystal': 'aux5'}})
# plans.append({'plan_name': 'johann_alignment_scan_plan_bundle',
#               'plan_kwargs': {'crystal': 'main',
#                               'alignment_plan': 'fly_scan_johann_elastic_alignment_plan_bundle',
#                               'fom': _scan_fom_dict['elastic']['alignment'],
#                               'alignment_data': bla,
#                               'e_cen': 8340, 'scan_range': 12, 'duration': 20, 'motor_info': 'main try2', 'md': {}}})
#
# plan_processor.add_plans(plans)
# plans = []
# plans.extend(johann_spectrometer_calibration_plan_bundle(calibrate_by='roll', scan_kind='fly', pil100k_roi_num=1, scan_range_roll=1000, scan_duration_roll=10))
# plan_processor.add_plans(plans)

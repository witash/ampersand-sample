from flask import request
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, IntegerField
from wtforms.validators import ValidationError, DataRequired, Length
from app.models import User


class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    about_me = TextAreaField('About me', validators=[Length(min=0, max=140)])
    submit = SubmitField('Submit')

    def __init__(self, original_username, *args, **kwargs):
        super(EditProfileForm, self).__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=self.username.data).first()
            if user is not None:
                raise ValidationError('Please use a different username.')

class EmptyForm(FlaskForm):
    submit = SubmitField('Submit')

class DriverForm(FlaskForm):
    phone_number = StringField('Enter phone number', validators=[DataRequired()])
    name = StringField('Enter given name', validators=[DataRequired()])
    #current_vehicle = TextAreaField(_l('Select current vehicle'), validators=[DataRequired()])
    submit = SubmitField('Submit')

class ChargingStationForm(FlaskForm):
    name = StringField('Enter given name', validators=[DataRequired()])
    submit = SubmitField('Submit')

class BatteryTransactionForm(FlaskForm):
    battery_out_id = SelectField('Select battery out', validators=[DataRequired()])
    driver_id = SelectField('Select Driver', validate_choice=False, validators=[DataRequired()])

    odometer_reading = IntegerField('Enter odometer reading', validators=[DataRequired()])
    battery_in_energy = IntegerField('Battery in energy', validators=[DataRequired()])
    battery_out_energy = IntegerField('Battery out energy', validators=[DataRequired()])
 
    submit = SubmitField('Submit')

class BatteryTransactionEditForm(FlaskForm):
    battery_out_id = SelectField('Select battery out', validators=[DataRequired()])
    battery_in_id = SelectField('Select battery in', validators=[DataRequired()])
    driver_id = SelectField('Select Driver', validate_choice=False, validators=[DataRequired()])

    odometer_reading = IntegerField('Enter odometer reading', validators=[DataRequired()])
    battery_in_energy = IntegerField('Battery in energy', validators=[DataRequired()])
    battery_out_energy = IntegerField('Battery out energy', validators=[DataRequired()])
 
    submit = SubmitField('Submit')

class BatteryForm(FlaskForm):
    capacity = TextAreaField('Enter capacity', validators=[DataRequired()]) 
    voltage = TextAreaField('Enter voltage', validators=[DataRequired()])
    submit = SubmitField('Submit')

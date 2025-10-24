from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Email

class UserForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired(), Length(min=2, max=30)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    lat = HiddenField("Latitude")
    lng = HiddenField("Longitude")
    consent = BooleanField("I agree to receive emails about weather alerts", validators=[DataRequired()])
    submit = SubmitField("Sign me Up!")